
# coding: utf-8
# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
import os
import pytest

from azure.core.credentials import AccessToken, AzureKeyCredential
from devtools_testutils import (
    AzureTestCase,
    AzureMgmtPreparer,
    FakeResource,
    ResourceGroupPreparer,
)
from devtools_testutils.cognitiveservices_testcase import CognitiveServicesAccountPreparer
from azure_devtools.scenario_tests import ReplayableTest

from azure.ai.language.questionanswering import QuestionAnsweringClient


REGION = 'westus2'


class FakeTokenCredential(object):
    """Protocol for classes able to provide OAuth tokens.
    :param str scopes: Lets you specify the type of access needed.
    """
    def __init__(self):
        self.token = AccessToken("YOU SHALL NOT PASS", 0)

    def get_token(self, *args):
        return self.token

TEST_ENDPOINT = 'https://test-resource.api.cognitive.microsoft.com'
TEST_KEY = '0000000000000000'
TEST_PROJECT = 'test-project'


class QuestionAnsweringTest(AzureTestCase):
    FILTER_HEADERS = ReplayableTest.FILTER_HEADERS + ['Ocp-Apim-Subscription-Key']

    def __init__(self, method_name):
        super(QuestionAnsweringTest, self).__init__(method_name)
        self.scrubber.register_name_pair(os.environ.get("QNA_ACCOUNT"), TEST_ENDPOINT)
        self.scrubber.register_name_pair(os.environ.get("QNA_KEY"), TEST_KEY)
        self.scrubber.register_name_pair(os.environ.get("QNA_PROJECT"), TEST_PROJECT)

    def get_oauth_endpoint(self):
        raise NotImplementedError()

    def generate_oauth_token(self):
        if self.is_live:
            from azure.identity import ClientSecretCredential
            return ClientSecretCredential(
                self.get_settings_value("TENANT_ID"),
                self.get_settings_value("CLIENT_ID"),
                self.get_settings_value("CLIENT_SECRET"),
            )
        return self.generate_fake_token()

    def generate_fake_token(self):
        return FakeTokenCredential()


class GlobalResourceGroupPreparer(AzureMgmtPreparer):
    def __init__(self):
        super(GlobalResourceGroupPreparer, self).__init__(
            name_prefix='',
            random_name_length=42
        )

    def create_resource(self, name, **kwargs):
        rg = FakeResource(
            name="rgname",
            id="/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rgname"
        )

        return {
            'location': REGION,
            'resource_group': rg,
        }


class GlobalQuestionAnsweringAccountPreparer(AzureMgmtPreparer):
    def __init__(self):
        super(GlobalQuestionAnsweringAccountPreparer, self).__init__(
            name_prefix='',
            random_name_length=42
        )

    def create_resource(self, name, **kwargs):
        if self.is_live:
            return {
                'location': REGION,
                'resource_group': "rgname",
                'qna_account': os.environ.get("QNA_ACCOUNT"),
                'qna_key': os.environ.get("QNA_KEY"),
                'qna_project': os.environ.get("QNA_PROJECT")
            }
        return {
            'location': REGION,
            'resource_group': "rgname",
            'qna_account': TEST_ENDPOINT,
            'qna_key': TEST_KEY,
            'qna_project': TEST_PROJECT
        }
