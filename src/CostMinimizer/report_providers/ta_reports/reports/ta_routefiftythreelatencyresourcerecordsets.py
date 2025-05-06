# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd
from rich.progress import track

class TaRoutefiftythreelatencyresourcerecordsets(TaBase):

    def name(self):
        return "ta_routefiftythreelatencyresourcerecordsets"

    def common_name(self):
        return "Amazon Route 53 Latency Resource Record Sets"

    def service_name(self):
        return "Trusted Advisor"

    def domain_name(self):
        return 'NETWORK'

    def description(self):
        return "Identifies Amazon Route 53 latency resource record sets that can be optimized"

    def long_description(self):
        return f'''This check analyzes your Amazon Route 53 latency resource record sets and identifies opportunities for optimization. 
        It examines the configuration of your latency-based routing policies and suggests improvements to enhance performance and reduce latency for your users.
        Results include:
        - Domain name and record set details
        - Current latency resource record set configuration
        - Recommendations for optimizing routing policies
        - Potential performance improvements
        Use this information to optimize your Route 53 latency-based routing and improve the responsiveness of your applications for users in different geographic locations.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows identifying Amazon Route 53 latency resource record sets that can be optimized'''

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
            return self.report_result[0]['Data'].shape[0]
        except Exception as e:
            self.appConfig.logger.warning(f"Error in counting rows: {str(e)}")
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
                    self.get_required_columns()[4]: resource['metadata'][4]
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': Name, 'Data': df, 'Type': type})

    def get_required_columns(self) -> list:
        return [
            'Domain Name',
            'Record Set Name',
            'Current Configuration',
            'Recommended Configuration',
            'Potential Performance Improvement'
        ]

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 10, 1, 10, -1