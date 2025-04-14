# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd

class TaAmazonecrwithoutlifecyclepolicy(TaBase):

    def name(self):
        return "ta_amazonecrwithoutlifecyclepolicy"

    def service_name(self):
        return "Trusted Advisor"

    def domain_name(self):
        return 'STORAGE'

    def common_name(self):
        return "Amazon ECR Repository Without Lifecycle Policy Configured"

    def description(self):
        return "Identifies Amazon ECR repositories without a lifecycle policy configured"

    def long_description(self) -> str:
        return f'''Identifies Trusted Advisor Amazon RDS Idle DB Instances recommendations.
        Checks the configuration of your Amazon Relational Database Service (Amazon RDS) for any DB instances that appear to be idle. 
        If a DB instance has not had a connection for a prolonged period of time, you can delete the instance to reduce costs. '''

    def author(self) -> list: 
        return ['slepetre']

    def report_provider(self):
        return 'ta'

    def report_type(self):
        return 'processed'

    def disable_report(self) -> bool:
        return False

    def display_in_menu(self) -> bool:
        return True

    def get_estimated_savings(self, sum=True) -> float:
        self._set_recommendation()
		
        return self.set_estimate_savings( sum)

    def set_estimate_savings(self, sum=False) -> float:
		
        df = self.get_report_dataframe()

        if sum and (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
            return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))
        else:
            return 0.0

    def _set_recommendation(self):
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend. No estimated savings recommendation is provided by this report.  Query provides account information useful for cost optimization.'''

    def count_rows(self) -> int:
        '''Return the number of rows found in the dataframe'''
        try:
            return self.calculate_savings().shape[0]
        except:
            return 0
	
    def calculate_savings(self):
        df = self.get_report_dataframe()
		
		#nothing to calculate for this check we just sum up the column
        return df

    def addTaReport(self, client, Name, CheckId):
        type = 'table'
        results = []

        response = client.describe_trusted_advisor_check_result(checkId=CheckId)

        data_list = []

        if response['result']['status'] == 'not_available':
            print(f"No resources found for checkid {CheckId}.")
        else:
            for resource in response['result']['flaggedResources']:
                data_dict = {
                    self.get_required_columns()[0]: resource['region'],
                    self.get_required_columns()[1]: resource['metadata'][1],
                    self.get_required_columns()[2]: resource['metadata'][2],
                    self.get_required_columns()[3]: resource['metadata'][3],
                    self.get_required_columns()[4]: int(resource['metadata'][4]),
                    self.get_required_columns()[5]: int(0.0)
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': Name, 'Data': df, 'Type': type})


    def get_required_columns(self) -> list:
        return [
                "Region",
                "Repository_name",
                "Repository_arn",
                "Created_at",
                "Image_count",
                self.ESTIMATED_SAVINGS_CAPTION
            ]

    # return range definition of the categories in the excel graph
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return range definition of the values in the excel graph
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 10, 1, 10, -1