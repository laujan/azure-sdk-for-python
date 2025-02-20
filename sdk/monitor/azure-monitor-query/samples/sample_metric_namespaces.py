# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from azure.monitor.query import MetricsQueryClient
from azure.identity import DefaultAzureCredential

credential  = DefaultAzureCredential()

client = MetricsQueryClient(credential)

metrics_uri = os.environ['METRICS_RESOURCE_URI']
response = client.list_metric_namespaces(metrics_uri)

for item in response:
    print(item.metric_namespace_name)
    print(item.type)
