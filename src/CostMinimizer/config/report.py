# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

class Report:
    def __init__(self, row):
        self.Id = row[0]
        self.Name = row[1]
        self.Description = row[2]
        self.Provider = row[3]
        self.ServiceName = row[4]
        self.Display = True if str(row[5]).lower() == "true" else False
        self.CommonName = row[6]
        self.LongDesc = row[7]
        self.DomainName = row[8]
        self.HtmlLink = row[9]
        self.DanteLink = row[10]
        self._row = row

    def __getitem__(self, key):
        return self._row[key]
