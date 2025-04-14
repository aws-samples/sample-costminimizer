# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd

class TaInactivenatagateways(TaBase):

    def name(self):
        return "ta_inactivenatagateways"

    def common_name(self):
        return "Inactive NAT Gateways"

    def description(self):
        return "Identifies inactive NAT Gateways that may be incurring unnecessary costs."

    def long_description(self):
        return """This check identifies NAT Gateways that are inactive but still incurring charges.
        NAT Gateways are used to enable instances in a private subnet to connect to the
        internet or other AWS services, but maintain private IP addresses. Inactive NAT
        Gateways continue to charge hourly usage and data processing rates, which can
        lead to unnecessary costs. Identifying and removing inactive NAT Gateways can
        help optimize your AWS expenses."""

    def author(self) -> list: 
        return ['slepetre']

    def domain_name(self):
        return 'NETWORK'

    def service_name(self):
        return "Trusted Advisor"

    def report_provider(self):
        return "ta"

    def report_type(self):
        return "processed"

    def disable_report(self):
        return False

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
        estimated_cost_unassigned_ip = 0.045 * 24 * 30
		
		#nothing to calculate for this check we just sum up the column
        return estimated_cost_unassigned_ip

    def count_rows(self) -> int:
        '''Return the number of rows found in the dataframe'''
        try:
            df = self.get_report_dataframe()
            return len(df)
        except:
            return 0

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
                    # Rename columns for better readability
                    self.get_required_columns()[0]: resource['metadata'][0],
                    self.get_required_columns()[1]: resource['metadata'][1],
                    self.get_required_columns()[2]: resource['metadata'][2],
                    self.get_required_columns()[3]: resource['metadata'][3],
                    self.get_required_columns()[4]: self.calculate_savings()
                    }

                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': Name, 'Data': df, 'Type': type})

    def get_required_columns(self):
        return [
            "Region",
            "NAT_Gateway_Id",
            "State",
            "CreationTime",
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