# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import os
from pathlib import Path

from ..utils.yaml_loader import import_yaml_file
from ..patterns.singleton import Singleton


class ToolingVersion(Singleton):

    def __init__(self) -> None:
        self.tooling_internals_from_file = {}

        self.app_path = Path(os.path.dirname(__file__))
        
        internals_file = self.app_path.parent / 'conf/tooling_internals.yaml'

        if internals_file.is_file():
            self.tooling_internals_from_file = import_yaml_file(internals_file)
            self.version = self.tooling_internals_from_file['internals']['version']
        else:
            self.version = ''

    def get_version(self, internal_version = "0.0.0"):
        if (self.version):
            return self.version
        else:
            return internal_version
        
    def update_version(self, version) -> str:
        self.version = version
        return self.version
