# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from ..version.version import ToolingVersion
from ..config.config import Config

class NotImplementedException(Exception):
    pass

class VersionCommand:

    def __init__(self, appInstance) -> None:
        #ToDo remove appInstance
        # self.appInstance = appInstance
        self.appConfig = Config()
        cv = ToolingVersion()
        self.version = cv.get_version(self.appConfig.internals['internals']['version'])

    def run(self):
        self.appConfig.console.print(f"Version : [yellow]{self.version}")