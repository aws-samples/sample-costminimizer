# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import platform


def determine_os():
    '''
    Windows = 'Windows'
    Mac = 'Darwin'
    Linux = 'Linux'
    '''
    
    return platform.system()

