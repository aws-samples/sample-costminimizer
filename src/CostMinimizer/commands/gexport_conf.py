# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..gexport_conf.gexport_conf import CowExportConf

class NotImplementedException(Exception):
    pass

class ExportConfCommand:
        
    def __init__(self, appConfig) -> None:
        self.appConfig = appConfig
        return

    def run(self):
        ce = CowExportConf(self.appConfig) #appInstance dependency removed
        ce.run()
        
        
