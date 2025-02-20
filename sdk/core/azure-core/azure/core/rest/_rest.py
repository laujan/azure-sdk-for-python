# --------------------------------------------------------------------------
#
# Copyright (c) Microsoft Corporation. All rights reserved.
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the ""Software""), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
# --------------------------------------------------------------------------
import copy
from json import loads

from typing import TYPE_CHECKING, cast

from azure.core.exceptions import HttpResponseError

from ..utils._utils import _case_insensitive_dict
from ._helpers import (
    FilesType,
    parse_lines_from_text,
    set_content_body,
    set_json_body,
    set_multipart_body,
    set_urlencoded_body,
    format_parameters,
    to_pipeline_transport_request_helper,
    from_pipeline_transport_request_helper,
    get_charset_encoding,
)
from ..exceptions import ResponseNotReadError
if TYPE_CHECKING:
    from typing import (
        Iterable,
        Optional,
        Any,
        Iterator,
        Union,
        Dict,
    )
    from ._helpers import HeadersType
    ByteStream = Iterable[bytes]
    ContentType = Union[str, bytes, ByteStream]

    from ._helpers import HeadersType, ContentTypeBase as ContentType



################################## CLASSES ######################################

class HttpRequest(object):
    """Provisional object that represents an HTTP request.

    **This object is provisional**, meaning it may be changed in a future release.

    It should be passed to your client's `send_request` method.

    >>> from azure.core.rest import HttpRequest
    >>> request = HttpRequest('GET', 'http://www.example.com')
    <HttpRequest [GET], url: 'http://www.example.com'>
    >>> response = client.send_request(request)
    <HttpResponse: 200 OK>

    :param str method: HTTP method (GET, HEAD, etc.)
    :param str url: The url for your request
    :keyword mapping params: Query parameters to be mapped into your URL. Your input
     should be a mapping of query name to query value(s).
    :keyword mapping headers: HTTP headers you want in your request. Your input should
     be a mapping of header name to header value.
    :keyword any json: A JSON serializable object. We handle JSON-serialization for your
     object, so use this for more complicated data structures than `data`.
    :keyword content: Content you want in your request body. Think of it as the kwarg you should input
     if your data doesn't fit into `json`, `data`, or `files`. Accepts a bytes type, or a generator
     that yields bytes.
    :paramtype content: str or bytes or iterable[bytes] or asynciterable[bytes]
    :keyword dict data: Form data you want in your request body. Use for form-encoded data, i.e.
     HTML forms.
    :keyword mapping files: Files you want to in your request body. Use for uploading files with
     multipart encoding. Your input should be a mapping of file name to file content.
     Use the `data` kwarg in addition if you want to include non-file data files as part of your request.
    :ivar str url: The URL this request is against.
    :ivar str method: The method type of this request.
    :ivar mapping headers: The HTTP headers you passed in to your request
    :ivar bytes content: The content passed in for the request
    """

    def __init__(self, method, url, **kwargs):
        # type: (str, str, Any) -> None

        self.url = url
        self.method = method

        params = kwargs.pop("params", None)
        if params:
            self.url = format_parameters(self.url, params)
        self._files = None
        self._data = None

        default_headers = self._set_body(
            content=kwargs.pop("content", None),
            data=kwargs.pop("data", None),
            files=kwargs.pop("files", None),
            json=kwargs.pop("json", None),
        )
        self.headers = _case_insensitive_dict(default_headers)
        self.headers.update(kwargs.pop("headers", {}))

        if kwargs:
            raise TypeError(
                "You have passed in kwargs '{}' that are not valid kwargs.".format(
                    "', '".join(list(kwargs.keys()))
                )
            )

    def _set_body(self, content, data, files, json):
        # type: (Optional[ContentType], Optional[dict], Optional[FilesType], Any) -> HeadersType
        """Sets the body of the request, and returns the default headers
        """
        default_headers = {}
        if data is not None and not isinstance(data, dict):
            # should we warn?
            content = data
        if content is not None:
            default_headers, self._data = set_content_body(content)
            return default_headers
        if json is not None:
            default_headers, self._data = set_json_body(json)
            return default_headers
        if files:
            default_headers, self._files = set_multipart_body(files)
        if data:
            default_headers, self._data = set_urlencoded_body(data, bool(files))
        return default_headers

    def _update_headers(self, default_headers):
        # type: (Dict[str, str]) -> None
        for name, value in default_headers.items():
            if name == "Transfer-Encoding" and "Content-Length" in self.headers:
                continue
            self.headers.setdefault(name, value)

    @property
    def content(self):
        # type: (...) -> Any
        """Get's the request's content

        :return: The request's content
        :rtype: any
        """
        return self._data or self._files

    def __repr__(self):
        # type: (...) -> str
        return "<HttpRequest [{}], url: '{}'>".format(
            self.method, self.url
        )

    def __deepcopy__(self, memo=None):
        try:
            request = HttpRequest(
                method=self.method,
                url=self.url,
                headers=self.headers,
            )
            request._data = copy.deepcopy(self._data, memo)
            request._files = copy.deepcopy(self._files, memo)
            return request
        except (ValueError, TypeError):
            return copy.copy(self)

    def _to_pipeline_transport_request(self):
        return to_pipeline_transport_request_helper(self)

    @classmethod
    def _from_pipeline_transport_request(cls, pipeline_transport_request):
        return from_pipeline_transport_request_helper(cls, pipeline_transport_request)

class _HttpResponseBase(object):  # pylint: disable=too-many-instance-attributes

    def __init__(self, **kwargs):
        # type: (Any) -> None
        self.request = kwargs.pop("request")
        self._internal_response = kwargs.pop("internal_response")
        self.status_code = None
        self.headers = {}  # type: HeadersType
        self.reason = None
        self.is_closed = False
        self.is_stream_consumed = False
        self.content_type = None
        self._json = None  # this is filled in ContentDecodePolicy, when we deserialize
        self._connection_data_block_size = None  # type: Optional[int]
        self._content = None  # type: Optional[bytes]

    @property
    def url(self):
        # type: (...) -> str
        """Returns the URL that resulted in this response"""
        return self.request.url

    @property
    def encoding(self):
        # type: (...) -> Optional[str]
        """Returns the response encoding. By default, is specified
        by the response Content-Type header.
        """
        try:
            return self._encoding
        except AttributeError:
            return get_charset_encoding(self)

    @encoding.setter
    def encoding(self, value):
        # type: (str) -> None
        """Sets the response encoding"""
        self._encoding = value

    @property
    def text(self):
        # type: (...) -> str
        """Returns the response body as a string"""
        encoding = self.encoding
        if encoding == "utf-8" or encoding is None:
            encoding = "utf-8-sig"
        return self.content.decode(encoding)

    def json(self):
        # type: (...) -> Any
        """Returns the whole body as a json object.

        :return: The JSON deserialized response body
        :rtype: any
        :raises json.decoder.JSONDecodeError or ValueError (in python 2.7) if object is not JSON decodable:
        """
        # this will trigger errors if response is not read in
        self.content  # pylint: disable=pointless-statement
        if not self._json:
            self._json = loads(self.text)
        return self._json

    def raise_for_status(self):
        # type: (...) -> None
        """Raises an HttpResponseError if the response has an error status code.

        If response is good, does nothing.
        """
        if cast(int, self.status_code) >= 400:
            raise HttpResponseError(response=self)

    @property
    def content(self):
        # type: (...) -> bytes
        """Return the response's content in bytes."""
        if self._content is None:
            raise ResponseNotReadError(self)
        return self._content

    def __repr__(self):
        # type: (...) -> str
        content_type_str = (
            ", Content-Type: {}".format(self.content_type) if self.content_type else ""
        )
        return "<HttpResponse: {} {}{}>".format(
            self.status_code, self.reason, content_type_str
        )

class HttpResponse(_HttpResponseBase):  # pylint: disable=too-many-instance-attributes
    """**Provisional** object that represents an HTTP response.

    **This object is provisional**, meaning it may be changed in a future release.

    It is returned from your client's `send_request` method if you pass in
    an :class:`~azure.core.rest.HttpRequest`

    >>> from azure.core.rest import HttpRequest
    >>> request = HttpRequest('GET', 'http://www.example.com')
    <HttpRequest [GET], url: 'http://www.example.com'>
    >>> response = client.send_request(request)
    <HttpResponse: 200 OK>

    :keyword request: The request that resulted in this response.
    :paramtype request: ~azure.core.rest.HttpRequest
    :ivar int status_code: The status code of this response
    :ivar mapping headers: The response headers
    :ivar str reason: The reason phrase for this response
    :ivar bytes content: The response content in bytes.
    :ivar str url: The URL that resulted in this response
    :ivar str encoding: The response encoding. Is settable, by default
     is the response Content-Type header
    :ivar str text: The response body as a string.
    :ivar request: The request that resulted in this response.
    :vartype request: ~azure.core.rest.HttpRequest
    :ivar internal_response: The object returned from the HTTP library.
    :ivar str content_type: The content type of the response
    :ivar bool is_closed: Whether the network connection has been closed yet
    :ivar bool is_stream_consumed: When getting a stream response, checks
     whether the stream has been fully consumed
    """

    def __enter__(self):
        # type: (...) -> HttpResponse
        return self

    def close(self):
        # type: (...) -> None
        self.is_closed = True
        self._internal_response.close()

    def __exit__(self, *args):
        # type: (...) -> None
        self.close()

    def read(self):
        # type: (...) -> bytes
        """
        Read the response's bytes.

        """
        if self._content is None:
            self._content = b"".join(self.iter_bytes())
        return self.content

    def iter_raw(self):
        # type: () -> Iterator[bytes]
        """Iterate over the raw response bytes
        """
        raise NotImplementedError()

    def iter_bytes(self):
        # type: () -> Iterator[bytes]
        """Iterate over the response bytes
        """
        raise NotImplementedError()

    def iter_text(self):
        # type: () -> Iterator[str]
        """Iterate over the response text
        """
        for byte in self.iter_bytes():
            text = byte.decode(self.encoding or "utf-8")
            yield text

    def iter_lines(self):
        # type: () -> Iterator[str]
        for text in self.iter_text():
            lines = parse_lines_from_text(text)
            for line in lines:
                yield line

    def _close_stream(self):
        # type: (...) -> None
        self.is_stream_consumed = True
        self.close()
