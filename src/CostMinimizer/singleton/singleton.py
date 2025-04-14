# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "samuel LEPETRE"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls.arguments_parsed = None
            # Put any initialization here.
        return cls._instance

    def some_business_logic(self):
        # Singleton-specific methods
        pass