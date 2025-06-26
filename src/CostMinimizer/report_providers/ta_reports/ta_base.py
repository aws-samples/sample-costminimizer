# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ...constants import __tooling_name__, __estimated_savings_caption__

import os
import sys
import logging
from abc import ABC
from pyathena.pandas.result_set import AthenaPandasResultSet
from ...report_providers.report_providers import ReportBase
import pandas as pd

# Required to load modules from vendored subfolder (for clean development env)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "./vendored"))


class TaBase(ReportBase, ABC):
    """Retrieves BillingInfo checks from TrustedAdvisor API
    """    
    def __init__(self, appConfig):

        super().__init__(appConfig)
        self.appConfig = appConfig

        self.ESTIMATED_SAVINGS_CAPTION = "Estimated_Monthly_Savings"

        try:
            self.client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('trustedadvisor', region_name=self.appConfig.default_selected_region)
        except Exception as e:
            self.appConfig.console.print(f'\n[red]Unable to establish boto session for TrustedAdvisor. \nPlease verify credentials in ~/.aws/ or Environment Variables like account ID, region and role ![/red]')
            sys.exit()

        try:
            self.accounts = self.appConfig.accounts_metadata
        except:
            logging.exception("Getting Account names failed")
            self.accounts = {}

        self.logger = logging.getLogger(__name__)
        self.reports = [] # returns list of report classes
        self.report_result = [] # returns list of report results
        self.reports_in_progress = []
        self.completed_reports = []
        self.failed_reports = []

        #CUR Reports specific variables 
        self.profile_name = None

        self.lookback_period = None
        self.output = None #output as json
        self.parsed_query = None #query after all substitutions and formating
        self.dependency_data= {}
        self.report_dependency_list = []  #List of dependent reports. 

        self.ESTIMATED_SAVINGS_CAPTION = __estimated_savings_caption__

    @staticmethod
    def name():
        '''return name of report type'''
        return 'ta'

    def get_caching_status(self) -> bool:
        return True

    def post_processing(self):
        pass

    def auth(self):
        '''set authentication, we use the AWS profile to authenticate into the AWS account which holds the CUR/Athena integration'''
        self.profile_name = self.appConfig.customers.get_customer_profile_name(self.appConfig.customers.selected_customer)
        self.logger.info(f'Setting {self.name()} report authentication profile to: {self.profile_name}')
    
    def setup(self, run_validation=False):
        '''setup instrcutions for cur report type'''
        
        pass

    def run(
        self, 
        imported_reports=None, 
        additional_input_data=None, 
        expiration_days=None, 
        type=None,
        display=True,
        cow_execution_type=None) -> None:
        '''
        run ce report provider

        imported_reports = may be provided, if not provided will be discovered
        additional_input_data = additional input into the generation of the cache hash
        expiration_days = for cache expiration
        type = base or None; base tells this method that report is not a dependency for another report
        display = boolean; tells run() wether to display output on terminal with the rich module
        '''

        display=self.set_display() #set display variable

        self.reports = self.import_reports_for_run(imported_reports) #import reports

        self.expiration_days = self.set_expiration_days(expiration_days) #set expiration days

        self.accounts, self.regions, self.customer = self.set_report_request_for_run()

        self.provider_run(additional_input_data, display)

        return self.reports_in_progress

    def run_additional_logic_for_provider(self, report_object, additional_input_data=None) -> None:
        self.additional_input_data = additional_input_data

    def _set_report_object(self, report):
        '''set the report object for run'''
        
        return report(self.query_paramaters, self.appConfig.auth_manager.aws_cow_account_boto_session)
   
    def get_query_result(self) -> AthenaPandasResultSet:
        '''return pandas object from pyathena async query'''
        
        try:
            df = None
            # if result is not empty
            if len(self.report_result) > 0:
                # check if 'Data' is a member of dict report_result
                if 'Data' in self.report_result[0]:
                    df = self.report_result[0]['Data']
                    if not self.report_result[0]['Data'].empty:
                        if self.ESTIMATED_SAVINGS_CAPTION in df.columns:
                            if df[self.ESTIMATED_SAVINGS_CAPTION].dtype != float and df[self.ESTIMATED_SAVINGS_CAPTION].dtype != int:
                                df[self.ESTIMATED_SAVINGS_CAPTION] = df[self.ESTIMATED_SAVINGS_CAPTION].str.replace('$', '').astype(float)
            return df
        except Exception as e:
            msg = f'Unable to get query result {self.name()}: {e}'
            self.logger.error(msg)
            result = None
        
        return result

    def get_report_dataframe(self, columns=None) -> AthenaPandasResultSet:

        return self.get_query_result()

    def generateExcel(self, writer):
        # Create a Pandas Excel writer using XlsxWriter as the engine.\
        workbook = writer.book

        for report in self.report_result:
            if report == [] or len(report['Data']) == 0:
                continue
                
            if report.get('chart_type_of_excel') == 'pivot':
                # Create pivot table using pandas
                df = report['Data']
                pivot_table = pd.pivot_table(
                    df,
                    values=['EstimatedMonthlySavings'],
                    index=['checkName', 'Status'],
                    columns=['Region'],
                    aggfunc={'EstimatedMonthlySavings': 'sum'},
                    margins=True
                )
                sheet_name = f"{report['Name']}_pivot"[:31]  # Excel sheet name length limit
                pivot_table.to_excel(writer, sheet_name=sheet_name)
                
                # Get the xlsxwriter workbook and worksheet objects
                worksheet = writer.sheets[sheet_name]
                
                # Add some formatting
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC',
                    'border': 1
                })
                
                # Write the column headers with the defined format
                for col_num, value in enumerate(pivot_table.columns.values):
                    worksheet.write(0, col_num + 1, value, header_format)
                    worksheet.set_column(col_num + 1, col_num + 1, 15)  # Set column width
                
                # Format the cost columns to use currency format
                money_format = workbook.add_format({'num_format': '$#,##0.00'})
                for col in range(len(pivot_table.columns)):
                    if 'EstimatedMonthlySavings' in str(pivot_table.columns[col]):
                        worksheet.set_column(col + 1, col + 1, 15, money_format)

            # Add a new worksheet
            worksheet = workbook.add_worksheet(report['Name'][:30])

            report['Data'].to_excel(writer, sheet_name=report['Name'][:30])

            if report['Type'] == 'chart':
                
                # Create a chart object.
                chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
                
                NumLines=len(report['Data'])
                chart.add_series({
                    'name':       [report['Name'][:30], 0, 7],                   # Cell = line:0-Col7 => estimatedMonthlySavingsAmount column header
                    'categories': [report['Name'][:30], 1, 4, NumLines, 4],      # Range = [line:1-Col:4 to Line:LAST_LINE-col:4] => currentInstanceType column values
                    'values':     [report['Name'][:30], 1, 7, NumLines, 7],      # Range = [line:1-Col:7 to Line:LAST_LINE-col:7] => estimatedMonthlySavingsAmount column values
                })
                chart.set_y_axis({'label_position': 'low'})
                chart.set_x_axis({'label_position': 'low'})
                worksheet.insert_chart('O2', chart, {'x_scale': 2.0, 'y_scale': 2.0})

    def sql(self, list_ta_checks): #required
		# Create an AWS Support client

        for check in list_ta_checks['checks']:
            if check['name'] == self.common_name():
                check_id = check['id']
                #print(f"The check ID for {self.common_name()} is: {check_id}")
                return { "Module": 'Trusted Advisor' , "ID": check_id, "Name":self.common_name(), "Category":"cost_optimizing" }

        self.appConfig.console.print(f"\n[red]The '{self.common_name()}' check was not found.[/red]")
        return {}