# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

class Customer:
    def __init__(self, row, account:str = None):
        self.Id = row[0]
        self.Name = row[1]
        self.EmailAddress = row[2]
        self.CreateTime = row[3]
        self.LastUsedTime = row[4]
        self.AwsProfile = row[5]
        self.SecretsAwsProfile = row[6]
        self.AthenaS3Bucket = row[7]
        self.CurDbName = row[8]
        self.CurDbTable = row[9]
        self.CurRegion = row[10]
        self.MinSpend = row[11]
        self.PayerAccount = str(account)
        self._row = row

        try:
            self.MinSpend = int(row[11])
        except:
            self.MinSpend = 0

        self.AccRegex = row[12]
        self.AccountEmail = row[13]

    def __getitem__(self, key):
        return self._row[key]
