# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

class NotImplementedException(Exception):
    pass

class EnabledReportsCommand:

    def __init__(self, app) -> None:
        pass

    def run(self):
        raise NotImplementedException(f'Requested functionality not yet implemented')