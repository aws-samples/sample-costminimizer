# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

class PrintHelpCommand:
        
    def __init__(self, appConfig) -> None:
        self.appConfig = appConfig

    def run(self):

        self.appConfig.get_arguments_parser().print_help()