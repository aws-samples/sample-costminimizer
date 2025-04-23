# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd
from rich.progress import track

class TaSavingsplan(TaBase):

    def name(self):
        return 'ta_savingsplan'

    def service_name(self):
        return 'Trusted Advisor'

    def domain_name(self):
        return 'COMPUTE'

    def common_name(self):
        return 'Savings Plan'

    def description(self):
        return 'Checks for potential savings using Savings Plan'

    def report_type(self):
        return 'processed'

    def disable_report(self):
        return False

    def report_provider(self):
        return 'ta'

    def report_type(self):
        return 'processed'

    def description(self):
        return "Identifies potential cost savings opportunities by utilizing AWS Savings Plans for EC2, Fargate, and Lambda usage."

    def long_description(self):
        return '''This report analyzes your AWS usage patterns and identifies opportunities to reduce costs 
        by leveraging Savings Plans. It provides recommendations for Compute Savings Plans 
        and EC2 Instance Savings Plans based on your historical usage. 
        The report includes estimated monthly savings and the percentage of 
        potential cost reduction for each recommendation.'''

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
		
		#nothing to calculate for this check we just sum up the column
        return df

    def count_rows(self) -> int:
        '''Return the number of rows found in the dataframe'''
        try:
            df = self.get_report_dataframe()
            return len(df)
        except:
            return 0

    def addTaReport(self, client, Name, CheckId, Display = True):
        type = 'table'
        results = []

        response = client.describe_trusted_advisor_check_result(checkId=CheckId)

        data_list = []

        if response['result']['status'] == 'not_available':
            print(f"No resources found for checkid {CheckId} - {Name}.")
        else:
            display_msg = f'[green]Running Trusted Advisor Report: {Name} / {self.appConfig.selected_regions[0]}[/green]'
            for resource in track(response['result']['flaggedResources'], description=display_msg):
                data_dict = {
                    # Rename columns for better readability
                    self.get_required_columns()[0]: resource['result']['resourcesSummary']['resourcesProcessed'],
                    self.get_required_columns()[1]: resource['result']['resourcesSummary']['resourcesFlagged'],
                    self.ESTIMATED_SAVINGS_CAPTION: resource['result']['categorySpecificSummary']['costOptimizing']['estimatedMonthlySavings'],
                    self.get_required_columns()[3]: resource['result']['categorySpecificSummary']['costOptimizing']['estimatedPercentMonthlySavings']
                    }

                data_list.append(data_dict)                
        
            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': Name, 'Data': df, 'Type': type})

    def get_required_columns(self) -> list:
        return [
                "resourcesProcessed",
                "resourcesFlagged",
                "estimatedMonthlySavings",
                "estimatedPercentMonthlySavings"
            ]

    # return range definition of the categories in the excel graph
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return range definition of the values in the excel graph
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 10, 1, 10, -1