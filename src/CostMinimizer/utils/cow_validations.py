# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

def aws_account_length(account):
    '''validate account number length is 12'''
    if isinstance(account, int):
        account = str(account)

    if len(account) == 12:
        return True

    return False

def pad_aws_account(account) -> str:
    '''return account number as string padded to 12 chars'''

    return str(account).zfill(12)
