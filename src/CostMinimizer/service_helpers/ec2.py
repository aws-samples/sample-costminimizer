# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from ..config.config import Config

class Ec2Query:

    def __init__(self):
        self.appConfig = Config()
    
    def get_instance_unblended_cost_from_cur(self, instance_id):
        df = self.appConfig.precondition_reports.precondition_reports_in_progress[0].get_report_dataframe()
        mask = df['line_item_resource_id'] == instance_id

        try:
            cost = float(df[mask].line_item_unblended_cost.values[0])
        except:
            cost = 0.0
        currency = 'usd'

        return cost, currency