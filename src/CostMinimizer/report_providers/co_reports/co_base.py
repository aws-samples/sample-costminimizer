# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"
from ...constants import __tooling_name__, __estimated_savings_caption__

import os
import sys
import datetime
import logging
import pandas as pd
#For date
from dateutil.relativedelta import relativedelta
from abc import ABC
from pyathena.pandas.result_set import AthenaPandasResultSet
from ...report_providers.report_providers import ReportBase
import boto3
from typing import List, Dict, Any
from dataclasses import dataclass
import numpy as np
import json
from rich.progress import track

from ...config.config import Config
from ...service_helpers.ec2 import Ec2Query
from ...report_controller.region_discovery_controller import RegionDiscoveryController
from ...service_helpers.pricing import PricingQuery


# Required to load modules from vendored subfolder (for clean development env)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "./vendored"))
logger = logging.getLogger(__name__)

class CoBase(ReportBase, ABC):
    """Retrieves BillingInfo checks from ComputeOptimizer API
    """    
    def __init__(self, appConfig):

        super().__init__( appConfig)
        self.appConfig = appConfig

        self.end = datetime.date.today().replace(day=1)
        self.riend = datetime.date.today()
        self.start = (datetime.date.today() - relativedelta(months=+12)).replace(day=1) #1st day of month 12 months ago
    
        self.ristart = (datetime.date.today() - relativedelta(months=+11)).replace(day=1) #1st day of month 11 months ago
        self.sixmonth = (datetime.date.today() - relativedelta(months=+6)).replace(day=1) #1st day of month 6 months ago, so RI util has savings values
        try:
            self.accounts = self.appConfig.accounts_metadata
        except Exception as e:
            #self.appConfig.
            logging.exception("Getting Account names failed")
            self.accounts = {}

        self.reports = [] # returns list of report classes
        self.report_result = [] # returns list of report results
        self.reports_in_progress = []
        self.completed_reports = []
        self.failed_reports = []

        self.ESTIMATED_SAVINGS_CAPTION = __estimated_savings_caption__
        
        #CUR Reports specific variables 
        self.profile_name = None

        self.lookback_period = None
        self.output = None #output as json
        self.parsed_query = None #query after all substitutions and formating
        self.dependency_data= {}
        self.report_dependency_list = []  #List of dependent reports.

    @staticmethod
    def name():
        '''return name of report type'''
        return 'co'

    def get_caching_status(self) -> bool:
        return True

    def post_processing(self):
        pass

    def auth(self):
        '''set authentication, we use the AWS profile to authenticate into the AWS account which holds the CUR/Athena integration'''
        self.profile_name = self.appConfig.customers.get_customer_profile_name(self.appConfig.customers.selected_customer)
        logger.info(f'Setting {self.name()} report authentication profile to: {self.profile_name}')
    
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

    def addCoReport(self, range_categories, range_values, list_cols_currency, group_by): #Call with Savings True to get Utilization report in dollar savings
        self.graph_range_values_x1, self.graph_range_values_y1, self.graph_range_values_x2,  self.graph_range_values_y2 = range_values
        self.graph_range_categories_x1, self.graph_range_categories_y1, self.graph_range_categories_x2,  self.graph_range_categories_y2 = range_categories
        self.list_cols_currency = list_cols_currency
        self.group_by = group_by
        # insert pivot type of graphs in the excel worksheet
        self.set_chart_type_of_excel()
        return self.report_result

    def get_query_fetchall(self) -> list:
        return self.get_query_result()

    def get_query_result(self) -> AthenaPandasResultSet:
        '''return pandas object from pyathena async query'''

        try:
            result = self.report_result[0]['Data']
        except Exception as e:
            msg = f'Unable to get query result self.report_result[0]: {e}'
            self.logger.error(msg)
            self.set_fail_query(reason=msg)
            result = None
        
        return result

    def get_report_dataframe(self, columns=None) -> AthenaPandasResultSet:
        
        try:
            self.fetched_query_result = self.get_query_fetchall()
        except:
            self.fetched_query_result = None

        return pd.DataFrame(self.fetched_query_result, columns=self.get_expected_column_headers())

    def set_workbook_formatting(self) -> dict:
        # set workbook format options
        fmt = {
            'savings_format': {'num_format': '$#,##0.00'},
            'default_column_format': {'align': 'left', 'valign': 'bottom', 'text_wrap': True},
            'large_description_format': {'align': 'left', 'valign': 'bottom', 'text_wrap': True},
            'comparison_column_format': {'num_format': '$#,##0', 'bold': True, 'font_color': 'red','align': 'right', 'valign': 'right', 'text_wrap': True},
            'header_format': {'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BC', 'border': 1}
        }
        return fmt

    def generateExcel(self, writer):
        # Create a Pandas Excel writer using XlsxWriter as the engine.\
        workbook = writer.book
        workbook_format = self.set_workbook_formatting()

        for report in self.report_result:
            if report == [] or len(report['Data']) == 0:
                continue

            report['Name'] = report['Name'][:31]
            worksheet_name = report['Name']
            df = report['Data']

            # Add a new worksheet
            worksheet = workbook.add_worksheet(report['Name'])

            # Convert specific columns to numeric type before writing
            for col in self.list_cols_currency:
                try:
                    df[df.columns[col-1]] = pd.to_numeric(df[df.columns[col-1]], errors='coerce')
                except:
                    continue

            df.to_excel(writer, sheet_name=report['Name'])

            # Format workbook columns in self.list_cols_currency as money
            for col_idx in self.list_cols_currency:
                col_letter = chr(65 + col_idx)
                worksheet.set_column(f"{col_letter}:{col_letter}", 30, workbook.add_format(workbook_format['savings_format']))