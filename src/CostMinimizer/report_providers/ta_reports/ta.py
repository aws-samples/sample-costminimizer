# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ...constants import __tooling_name__

"""
Cost Explorer Report

A script, for local or lambda use, to generate CostExplorer excel graphs

"""

import os
import sys
import boto3
import logging
from ...report_providers.report_providers import ReportProviderBase
from rich.progress import track
from pathlib import Path


# Required to load modules from vendored subfolder (for clean development env)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "./vendored"))

class TaReports(ReportProviderBase):
    """Retrieves BillingInfo checks from CostExplorer API
    >>> costexplorer = CostExplorer()
    >>> costexplorer.addReport(GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"}])
    >>> costexplorer.generateExcel()
    """    
    def __init__(self, appConfig):

        super().__init__(appConfig)
        self.appConfig = appConfig
        self.config = appConfig.config

        #Array of reports ready to be output to Excel.
        self.reports = []
        self.accounts = {}

        self.logger = logging.getLogger(__name__)

        self.report_path = self.appConfig.internals['internals']['reports']['reports_directory']
        self.report_directory = Path()
        try:
            # First attempt to find reports folder
            self.report_directory = Path(os.getcwd()) / self.report_path / self.appConfig.internals['internals']['ta_reports']['ta_directory'] / self.appConfig.internals['internals']['ta_reports']['report_directory']
            os.listdir(self.report_directory)
        except (OSError, FileNotFoundError):
            try:
                # Second attempt in src directory
                self.report_directory = Path(os.getcwd()) / "src" / __name__.split('.')[0] / self.report_path / self.appConfig.internals['internals']['ta_reports']['ta_directory'] / self.appConfig.internals['internals']['ta_reports']['report_directory']
                os.listdir(self.report_directory)
            except (OSError, FileNotFoundError) as e:
                self.logger.error(f'Unable to find the reports folder, either under {os.getcwd()} or src/')
                raise RuntimeError("Reports directory not found") from e

        self.reports = None # returns list of report classes
        self.list_reports_results = [] # returns list of reports results
        self.reports_in_progress = []
        self.completed_reports = []
        self.failed_reports = []
        self.list_ta_checks = []
        self.succeeded_queries = []
    
    @staticmethod
    def name():
        '''return name of report type'''
        return 'ta'


    def long_name(self):
        '''return name for app.console'''
        return 'Trusted Advisor'

    def auth(self):
        '''set authentication, we use the AWS profile to authenticate into the AWS account which holds the CUR/Athena integration'''
        self.profile_name = 'detault'
        self.logger.info(f'Setting {self.name()} report authentication profile to: {self.profile_name}')
    
    def setup(self, run_validation=False):
        '''setup instrcutions for ta report type'''
                #Array of reports ready to be output to Excel.
        try:
            self.client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('support')
        except Exception as e:
            self.appConfig.console.print(f'\n[red]Unable to establish boto session for TrustedAdvisor. \n{e}[/red]')
            sys.exit()

    def run_additional_logic_for_provider(self, report_object, additional_input_data=None) -> None:
        self.additional_input_data = additional_input_data

    def _set_report_object(self, report):
        '''set the report object for run'''
        
        return report( self.appConfig)

    def import_reports_for_run(self, imported_reports):

        if imported_reports:
            reports = imported_reports
        else:
            reports = self.import_reports()

        return reports
        
    def run(
        self, 
        imported_reports=None, 
        additional_input_data=None, 
        expiration_days=None, 
        type=None,
        display=True,
        cow_execution_type=None) -> None:
        '''
        run cur report provider

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

    def execute_report(self, report_object, display, cached=False):

        def run_query( report_object, display = True):
            try:

                TaQuery = report_object.sql(self.list_ta_checks)

                if (TaQuery):
                    Name=TaQuery.get("Name", self.long_name())
                    Id=TaQuery.get("ID", '???')

                    if report_object.service_name() == self.long_name():
                        report_object.addTaReport( self.client , Name, Id, display)

                    self.logger.info(f'Running Trusted Advisor query: {report_name} ')
            except Exception as e:
                self.logger.error('Exception occured when during execution of TA query')
                self.logger.exception(e)
                self.appConfig.console.print(f'\n[red underline]Exception occured when during execution of TA query >>> {e}')
                sys.exit()

        try:
            self.list_ta_checks = self.client.describe_trusted_advisor_checks(language='en')
        except Exception as e:
            self.logger.error('Exception occured when during execution of TA query')
            self.logger.exception(e)
            self.appConfig.console.print(f'\n[red underline]Exception occured when during execution of TA query {e}')
            sys.exit()

        report_name = report_object.name()
        
        display_msg = f'[green]Running Trusted Advisor Report: {report_name} / {self.appConfig.selected_regions[0]}[/green]'
        
        if cached:
            for _ in track(range(1), description=display_msg + ' [yellow]CACHED'):
                pass

        else:
            if display:
                run_query(  report_object, True)
            else:
                run_query( report_object = False)

    def fetch_data(self, 
        reports_in_progress:list, 
        additional_input_data=None, 
        expiration_days=None, 
        type=None,
        display=True,
        cow_execution_type=None):

        if expiration_days is None:
            if (self.appConfig.get_cache_settings() != ''):
                expiration_days = self.appConfig.get_cache_settings()['report']
            else:
                expiration_days = 8
        
        # check on query state
        for report in reports_in_progress:
            if self.name() != report.report_provider():
                continue

            q = report
            q.status = 'UNKNOWN'

            report_name = q.name()

            if self.appConfig.auth_manager.appInstance.AppliConf.cow_execution_type == 'sync':

                self.logger.info(f'Getting status of report {report_name}')

                cache_status = q.get_caching_status()

                if cache_status ==False:
                    self.delete_cache_file(report_name, self.accounts, self.regions, self.customer, additional_input_data)

                if not self.check_cached_data(report_name, self.accounts, self.regions, self.customer, additional_input_data, expiration_days) or cache_status == False:
                    cache_status = q.get_caching_status()

                if cache_status ==False:
                    self.delete_cache_file(report_name, self.accounts, self.regions, self.customer, additional_input_data)

                #if not self.check_cached_data(report_name, accounts, regions, customer, additional_input_data, expiration_days) or cache_status == False:
                    
                q.execution_state = True
                self.logger.info(f'TA report query state reported : {q.name()}')

                #dump CUR data to cache
                #self.write_cache_data(report_name, report, accounts, regions, customer, additional_input_data)
                q.post_processing()

                self.succeeded_queries.append(q)
                self.completed_reports.append(q)

                self.logger.info(f'Data TA {q.name()} not found in cache.')

    def _make_cursor(self, async_cursor=True):
        '''make pyathena cursor - run in async pandas mode - see https://pypi.org/project/pyathena/#asyncpandascursor'''
        return

    def _make_boto3_client(self):
        session = boto3.Session(profile_name=self.profile_name)
        return session 

    def show_columns(self) -> list:
        '''show columns present in customer cur table.'''

        '''for column caching we don't care about accounts and regions, we only care about the customer name'''
        return

    def show_partitions(self) -> list:
        '''show partitions present in cursomer cur table.'''
        return

    def identify_partition_format(self, supported_partitions_list):
        """return partition format for month either 'mm' or 'm'"""
        return
        
    def get_partition_format(self):
        #cache partition format inside the sqllite database
        return

    def set_query_parameters(self) -> None:
        '''Set query parameters to pass to all available/enabled queries'''
        return

    def calculate_savings(self):
        '''
        for each successfully completed report that or type processed
        run the calculate savings method to determine estimated savings
         '''
        '''calculate savings for report'''
        successful_calculations = []
        return 0

    def get_data(self):
        for query in self.succeeded_queries:
            return query.dataframe 

    def get_status_by_execution_id(self, execution_id, report=None, async_cow=False, db_write=True):
        '''get query state
        execution_id = id of async query or call
        report = report object
        '''
