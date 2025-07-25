# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"
from ...constants import __tooling_name__

"""
Compute Optimizer Report

A script, for local or lambda use, to generate ComputeOptimizer excel graphs

"""

import os
import sys
# Required to load modules from vendored subfolder (for clean development env)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "./vendored"))

import boto3
import logging
#For email
from ...report_providers.report_providers import ReportProviderBase
from ...config.config import Config
from rich.progress import track
from pathlib import Path

class CoReports(ReportProviderBase):
    """Retrieves BillingInfo checks from CostExplorer API
    """    
    def __init__(self, appConfig):

        super().__init__( appConfig)
        self.appConfig = Config()

        #Array of reports ready to be output to Excel.
        self.reports = []
        self.accounts = {}

        self.logger = logging.getLogger(__name__)
        self.report_path = self.appConfig.internals['internals']['reports']['reports_directory']
        self.report_directory = Path()
        try:
            # First attempt to find reports folder
            self.report_directory = Path(os.getcwd()) / self.report_path / self.appConfig.internals['internals']['co_reports']['co_directory'] / self.appConfig.internals['internals']['co_reports']['report_directory']
            os.listdir(self.report_directory)
        except (OSError, FileNotFoundError):
            try:
                # Second attempt in src directory
                self.report_directory = Path(os.getcwd()) / "src" / __name__.split('.')[0] / self.report_path / self.appConfig.internals['internals']['co_reports']['co_directory'] / self.appConfig.internals['internals']['co_reports']['report_directory']
                os.listdir(self.report_directory)
            except (OSError, FileNotFoundError) as e:
                self.logger.error(f'Unable to find the reports folder, either under {os.getcwd()} or src/')
                raise RuntimeError("Reports directory not found") from e

        self.reports = None # returns list of report classes
        self.list_reports_results = [] # returns list of reports results
        self.reports_in_progress = []
        self.completed_reports = []
        self.failed_reports = []
        self.succeeded_queries = []

    @staticmethod
    def name():
        '''return name of report type'''
        return 'co'

    def long_name(self):
        '''return name for app.console'''
        return 'Compute Optimizer'

    def auth(self):
        pass
    
    def determine_co_enrollment_status(self) -> bool:
        try:
            response = self.client.get_enrollment_status()
            if response['status'] == 'Active':
                return True
        except Exception as e:
            self.appConfig.console.print(f'\n[red]Unable to determine Compute Optimizer enrollment status. \n{e}[/red]')
            self.logger.error('Unable to determine Compute Optimizer enrollment status.')
            sys.exit()
        return False

    def prerequisite(self):
        '''run all prerequisites for co to be able to run'''
        if self.determine_co_enrollment_status():
            self.appConfig.console.print(f'\n[green]Compute Optimizer is enrolled.[/green]')
            self.enrollment_status = True
        else:
            self.appConfig.console.print(f'\n[red]Compute Optimizer is not enrolled.[/red]')
            self.enrollment_status = False

    def setup(self, run_validation=False):
        '''setup instrcutions for cur report type'''
        try:
            self.client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('compute-optimizer', region_name=self.appConfig.selected_regions)
        except Exception as e:
            self.appConfig.console.print(f'\n[red]Unable to establish boto session for Compute-Optimizer. \n{e}[/red]')
            self.logger.error('Unable to establish boto session for Compute-Optimizer.')
            sys.exit()

        '''run any prerequisite checks'''
        self.prerequisite()

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

        def run_query(report_object, display = False, report_name = ''):
            try:
                region = self.regions
                account = self.accounts
                report_object.sql(self.client, region, account, display = display, report_name = report_name)

                Name= self.long_name()

                if report_object.service_name() == self.long_name():
                        report_object.addCoReport( 
                            report_object.get_range_categories() , 
                            report_object.get_range_values(),
                            report_object.get_list_cols_currency(),
                            report_object.get_group_by())

                self.logger.info(f'Running Compute Optimizer query: {report_name} ')
            except Exception as e:
                self.logger.error('Exception occured when during execution of CO query')
                self.logger.exception(e)
                self.appConfig.console.print(f'\n[red]Exception occured when during execution of CO query >>> {e}')
                sys.exit()


        report_name = report_object.name()
        
        display_msg = f'[green]Running Compute Optimizer Report: {report_name} / {self.appConfig.selected_regions}[/green]'
        
        if cached:
            for _ in track(range(1), description=display_msg + ' [yellow]CACHED'):
                pass

        else:
            if display:
                # execute report for all accounts/regions
                run_query(report_object, display, report_name)
            else:
                run_query(report_object)

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

            if self.appConfig.cow_execution_type == 'sync':

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
                self.logger.info(f'ComputeOptimizer report query state reported : {q.name()}')
                    
                    
                #q.dataframe = q.get_report_dataframe()
                #q.output = q.dataframe.to_json()
                    
                #dump CUR data to cache
                #self.write_cache_data(report_name, report, accounts, regions, customer, additional_input_data)
                q.post_processing()

                self.succeeded_queries.append(q)
                self.completed_reports.append(q)

                self.logger.info(f'Data ComputeOptimizer {q.name()} not found in cache.')

    def fetch_report_data_for_async(self, execution_id) -> list:
        '''fetch report data for async execution'''
        data = []

        return data

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
        run the calculate savings method to set estimated savings
         '''
        
        for report in self.reports_in_progress:
            #if report.status() == 'SUCCESS':
            report.get_estimated_savings(sum=True)


    def get_data(self):
        for query in self.succeeded_queries:
            return query.dataframe 

    def get_status_by_execution_id(self, execution_id, report=None, async_cow=False, db_write=True):
        '''get query state
        execution_id = id of async query or call
        report = report object
        '''

