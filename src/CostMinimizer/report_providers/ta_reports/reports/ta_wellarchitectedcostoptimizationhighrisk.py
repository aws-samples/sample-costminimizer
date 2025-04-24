# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd
from rich.progress import track

class TaWellarchitectedcostoptimizationhighrisk(TaBase):

    def name(self):
        return "ta_wellarchitectedcostoptimizationhighrisk"

    def common_name(self):
        return "AWS Well-Architected high risk issues for cost optimization"

    def service_name(self):
        return "Trusted Advisor"

    def domain_name(self):
        return 'MANAGEMENT'

    def description(self):
        return "Identifies high risk issues in the AWS Well-Architected Framework's cost optimization pillar"

    def long_description(self):
        return f'''This check analyzes your AWS infrastructure against the AWS Well-Architected Framework's cost optimization pillar and identifies high risk issues. 
        It examines your resource utilization, cost allocation, and spending patterns to highlight areas that may benefit from optimization.
        Results include:
        - Identified high risk issues
        - Affected resources or services
        - Potential cost impact
        - Recommended actions for mitigation
        Use this information to address high risk areas in your cost optimization strategy and improve your overall AWS architecture.'''

    def author(self) -> list: 
        return ['ai-generated']

    def report_provider(self):
        return "ta"

    def report_type(self):
        return "processed"

    def disable_report(self):
        return False

    def get_estimated_savings(self, sum=True) -> float:
        self._set_recommendation()
        
        return self.set_estimate_savings(True)

    def set_estimate_savings(self, sum=False) -> float:
        
        df = self.get_report_dataframe()

        if sum and (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
            return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))
        else:
            return 0.0

    def _set_recommendation(self):
        self.recommendation = f'''Returned {self.count_rows()} rows identifying high risk issues in the AWS Well-Architected Framework's cost optimization pillar'''

    def calculate_savings(self):
        df = self.get_report_dataframe()
        
        #nothing to calculate for this check we just sum up the column
        return df

    def count_rows(self) -> int:
        '''Return the number of rows found in the dataframe'''
        try:
            return self.calculate_savings().shape[0]
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
                    self.get_required_columns()[0]: resource['metadata'][0],
                    self.get_required_columns()[1]: resource['metadata'][1],
                    self.get_required_columns()[2]: resource['metadata'][2],
                    self.get_required_columns()[3]: resource['metadata'][3],
                    self.get_required_columns()[4]: resource['metadata'][4],
                    self.get_required_columns()[5]: resource['metadata'][5],
                    self.get_required_columns()[6]: resource['metadata'][6],
                    self.get_required_columns()[7]: resource['metadata'][7],
                    self.get_required_columns()[8]: resource['metadata'][8],
                    self.get_required_columns()[9]: resource['metadata'][9],
                    self.get_required_columns()[10]: resource['metadata'][10],
                    self.get_required_columns()[11]: resource['metadata'][11],
                    self.get_required_columns()[12]: resource['metadata'][12]
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': Name, 'Data': df, 'Type': type})

    def get_required_columns(self) -> list:
        return [
            'Status',
            'Region',
            'Workload ARN',
            'Workload Name',
            'Reviewer Name',
            'Workload Type',
            'Workload Started Date',
            'Workload Last Modified Date',
            '# of identified HRIs for Cost Optim',
            '# of HRIs resolved for Cost Optim',
            '# of questions answered for Cost Optim',
            'Total num. of questions in Cost Optim',
            'Last Updated Time'
        ]

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 10, 1, 10, -1