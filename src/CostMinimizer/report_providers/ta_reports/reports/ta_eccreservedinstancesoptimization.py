# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd
from rich.progress import track

class TaEccreservedinstancesoptimization(TaBase):

    def name(self):
        return "ta_eccreservedinstancesoptimization"

    def common_name(self):
        return "Amazon EC2 Reserved Instances Optimization"

    def service_name(self):
        return "Trusted Advisor"

    def domain_name(self):
        return 'COMPUTE'

    def description(self):
        return "Identifies potential cost savings by optimizing Amazon EC2 Reserved Instances"

    def long_description(self):
        return f'''This check analyzes your Amazon EC2 usage patterns and identifies opportunities to optimize your Reserved Instance purchases. 
        It compares your current EC2 usage with your existing Reserved Instances and suggests potential modifications or new purchases that could lead to cost savings. 
        The check considers factors such as instance types, regions, and usage patterns to provide tailored recommendations.
        Results include:
        - Current EC2 instance usage and existing Reserved Instance coverage
        - Recommendations for new Reserved Instance purchases or modifications
        - Potential cost savings from implementing the recommendations
        Use this information to optimize your Amazon EC2 costs by making informed decisions about Reserved Instance purchases and utilization.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from optimizing Amazon EC2 Reserved Instances'''

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
                    self.get_required_columns()[0]: resource['metadata'][1],
                    self.get_required_columns()[1]: resource['metadata'][0],
                    self.get_required_columns()[2]: resource['metadata'][2],
                    self.get_required_columns()[3]: resource['metadata'][3],
                    self.get_required_columns()[4]: resource['metadata'][4],
                    self.get_required_columns()[5]: resource['metadata'][5],
                    self.get_required_columns()[6]: resource['metadata'][6],
                    self.get_required_columns()[7]: resource['metadata'][7],
                    self.get_required_columns()[8]: resource['metadata'][8]
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': Name, 'Data': df, 'Type': type})

    def get_required_columns(self) -> list:
        return [
            'Region',
            'Instance Type',
            'OS',
            'Current On-Demand Instances',
            'Recommended RI Purchase',
            'Estimated Monthly Savings',
            'Upfront RI Cost',
            'Estimated Break-Even (Months)',
            'Estimated Savings over RI Term'
        ]

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 10, 1, 10, -1