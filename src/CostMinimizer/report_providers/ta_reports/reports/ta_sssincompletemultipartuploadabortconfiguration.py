# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd
from rich.progress import track

class TaSssincompletemultipartuploadabortconfiguration(TaBase):

    def name(self):
        return "ta_sssincompletemultipartuploadabortconfiguration"

    def service_name(self):
        return "Trusted Advisor"

    def domain_name(self):
        return "STORAGE"

    def common_name(self):
        return "S3 Incomplete Multipart Upload Abort Configuration"

    def description(self):
        return "Checks if S3 buckets have an incomplete multipart upload abort configuration."

    def long_description(self):
        return """This check examines your Amazon S3 buckets to ensure they have an appropriate configuration
        for aborting incomplete multipart uploads. Incomplete multipart uploads can accumulate over time,
        consuming storage and potentially incurring unnecessary costs. By configuring an abort rule,
        you can automatically remove incomplete multipart uploads after a specified number of days,
        helping to optimize storage usage and reduce costs."""
    def author(self) -> list: 
        return ['slepetre']

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
            display_msg = f'[green]Running Trusted Advisor Report: {Name} / {self.appConfig.selected_regions}[/green]'
            for resource in track(response['result']['flaggedResources'], description=display_msg):
                data_dict = {
                    # Rename columns for better readability
                    self.get_required_columns()[0]: resource['metadata'][0],
                    self.get_required_columns()[1]: resource['metadata'][1],
                    self.get_required_columns()[2]: resource['metadata'][2],
                    self.get_required_columns()[3]: resource['metadata'][3],
                    self.get_required_columns()[4]: resource['metadata'][4],
                    self.get_required_columns()[6]: resource['metadata'][5],
                    self.get_required_columns()[6]: resource['metadata'][6],
                    self.get_required_columns()[7]: int(0.0)
                    }

                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': Name, 'Data': df, 'Type': type})

    def get_required_columns(self):
        return ["Color", 
                "Bucket_Region", 
                "Bucket_Name", 
                "Bucket_Arn", 
                "Blob", 
                "Blob2", 
                "Datetime", 
                self.ESTIMATED_SAVINGS_CAPTION]

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 10, 1, 10, -1