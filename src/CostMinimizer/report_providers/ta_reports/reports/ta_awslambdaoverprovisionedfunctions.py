# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd
from rich.progress import track

class TaAwslambdaoverprovisionedfunctions(TaBase):

    def get_report_parameters(self) -> dict:

		#{report_name:[{'parameter_name':'value','current_value':'value','allowed_values':['val','val','val']} ]}
        return {'TrustedAdvisor checks':[{'parameter_name':'lookback_period','current_value':30,'allowed_values':['1','2','3','4','5','6']} ]}

    def name(self):
        return 'ta_awslambdaoverprovisionedfunctions'

    def common_name(self):
        return 'AWS Lambda over-provisioned functions for memory size'

    def service_name(self):
        return "Trusted Advisor"
	
    def domain_name(self):
        return 'COMPUTE'

    def report_provider(self):
        return 'ta'

    def report_type(self):
        return 'processed'

    def description(self):
        return "Identifies AWS Lambda functions that are over-provisioned for memory size"

    def long_description(self):
        return f'''Identifies AWS Lambda functions that are over-provisioned for memory size. This check:
        1. Analyzes Lambda function configurations and execution metrics
        2. Identifies functions with allocated memory significantly higher than peak usage
        3. Estimates potential cost savings from rightsizing memory allocations
        4. Helps optimize Lambda costs without impacting performance
        Recommendations: Review identified functions and consider reducing allocated memory
        to match actual needs, balancing performance and cost-efficiency.'''

    def author(self) -> list: 
        return ['slepetre']

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

    def calculate_savings(self):
        df = self.get_report_dataframe()
        try:
            if (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
                return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))
            else:
                return 0.0
        except:
            return 0.0

    def count_rows(self) -> int:
        try:
            return self.report_result[0]['Data'].shape[0] if not self.report_result[0]['Data'].empty else 0
        except Exception as e:
            self.appConfig.logger.warning(f"Error in {self.name()}: {str(e)}")
            return 0

    def addTaReport(self, client, Name, CheckId, Display = True):
        type = 'table'
        results = []

        response = client.describe_trusted_advisor_check_result(checkId=CheckId)

        data_list = []

        # if there is no resource for the specific checkid
        if response['result']['status'] == 'not_available':
            print(f"No resources found for checkid {CheckId} - {Name}.")
            self.report_result.append({'Name': Name, 'Data': pd.DataFrame(), 'Type': type})
        else:
            # Process and store the Lambda function data as needed
            display_msg = f'[green]Running Trusted Advisor Report: {Name} / {self.appConfig.selected_regions}[/green]'
            for resource in track(response['result']['flaggedResources'], description=display_msg):
                data_dict = {
                    self.get_required_columns()[0]: resource['metadata'][0],
                    self.get_required_columns()[1]: resource['metadata'][1],
                    self.get_required_columns()[2]: resource['metadata'][2],
                    self.get_required_columns()[3]: resource['metadata'][3],
                    self.get_required_columns()[4]: int(0.0)
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': Name, 'Data': df, 'Type': type})


    def get_required_columns(self) -> list:
        return [
                "Region",
                "Function_name",
                "configured_memory",
                "recommended_memory",
                self.ESTIMATED_SAVINGS_CAPTION
            ]

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 4, 1, 4, -1