# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd

class TaAwsaccountnotpartoforganizations(TaBase):

    def get_report_parameters(self) -> dict:

		#{report_name:[{'parameter_name':'value','current_value':'value','allowed_values':['val','val','val']} ]}
        return {'TrustedAdvisor checks':[{'parameter_name':'lookback_period','current_value':30,'allowed_values':['1','2','3','4','5','6']} ]}

    def name(self):
        return "ta_awsaccountnotpartoforganizations"

    def common_name(self):
        return "AWS Account Not Part of AWS Organizations"

    def description(self):
        return "Identifies if the AWS account is not part of an AWS Organizations"

    def long_description(self):
        return f'''Checks if the AWS account is not part of an AWS Organizations.
        Purpose: This check identifies AWS accounts that are standalone and not integrated into AWS Organizations.
        Benefits of AWS Organizations: Centralized management of multiple AWS accounts, consolidated billing
        , hierarchical groupings of accounts, and centralized policy management.
        Risks of non-participation: Standalone accounts miss out on cost savings, 
        simplified account management, enhanced security controls, and streamlined compliance offered by AWS Organizations.
        Recommendation: Consider joining or creating an AWS Organization to leverage these benefits 
        and improve overall account management and security posture.'''

    def author(self) -> list: 
        return ['slepetre']

    def service_name(self):
        return "Trusted Advisor"
	
    def domain_name(self):
        return 'ORGANIZATION'

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend. No estimated savings recommendation is provided by this report. Query provides account information useful for cost optimization.'''


    def calculate_savings(self):
        df = self.get_report_dataframe()
		
		#nothing to calculate for this check we just sum up the column
        return df

    def count_rows(self) -> int:
        '''Return the number of rows found in the dataframe'''
        try:
            df = self.get_report_dataframe()
            return len(df)
        except:
            return 0
	
    def calculate_savings(self):
        df = self.get_report_dataframe()
		
		#nothing to calculate for this check we just sum up the column 'ebs_gp3_potential_savings'
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
                    self.get_required_columns()[0]: resource['metadata'][0],
                    self.get_required_columns()[1]: resource['metadata'][1],
                    self.get_required_columns()[2]: resource['metadata'][2],
                    self.get_required_columns()[3]: resource['metadata'][3],
                    self.get_required_columns()[4]: resource['metadata'][4],
                    self.get_required_columns()[5]: resource['metadata'][5]
                }
                data_list.append(data_dict)

        df = pd.DataFrame(data_list)
        self.report_result.append({'Name': Name, 'Data': df, 'Type': type})


    def get_required_columns(self) -> list:
        return [
            'Status',
            'Region',
            'Resource',
            'AWS Config Rule',
            'Input Parameters',
            'Last Updated Time'
            ]

    # return range definition of the categories in the excel graph
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return range definition of the values in the excel graph
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 10, 1, 10, -1