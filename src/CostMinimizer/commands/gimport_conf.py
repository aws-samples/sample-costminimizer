# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from ..gimport_conf.gimport_conf import CowImportConf

class NotImplementedException(Exception):
    pass

class ImportConfCommand:

    def __init__(self, appConfig) -> None:
        self.appConfig = appConfig
        return

    def run(self):
        ci = CowImportConf(self.appConfig)
        ci.run()