# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ...constants import __tooling_name__

import sys, os
import logging
import datetime as time
from rich.progress import track
import pandas as pd
import json
from ...report_providers.report_providers import ReportProviderBase
from pathlib import Path
from ...config.config import Config


class CurReports(ReportProviderBase):
    """Retrieves BillingInfo from AWS CUR using Athena
    >>> cur_reports = CurReports()
    >>> cur_reports.addReport(GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"}])
    >>> cur_reports.generateExcel()
    """    
    def __init__(self, appConfig):

        super().__init__(appConfig)
        self.appConfig = Config()

        #CUR Reports specific variables 
        self.profile_name = None
        self.cur_s3_bucket = None
        self.cur_db = None
        self.cur_table = None
        self.cur_region = 'us-east-1'
        self.fqdb_name = None
        self._cursor = None
        self.query_parameters = None
        self.succeeded_queries = []

        self.logger = logging.getLogger(__name__)

        self.report_path = self.appConfig.internals['internals']['reports']['reports_directory']
        self.report_directory = Path()
        try:
            # First attempt to find reports folder
            self.report_directory = Path(os.getcwd()) / self.report_path / self.appConfig.internals['internals']['cur_reports']['cur_directory'] / self.appConfig.internals['internals']['cur_reports']['report_directory']
            os.listdir(self.report_directory)
        except (OSError, FileNotFoundError):
            try:
                # Second attempt in src directory
                self.report_directory = Path(os.getcwd()) / "src" / __name__.split('.')[0] / self.report_path / self.appConfig.internals['internals']['cur_reports']['cur_directory'] / self.appConfig.internals['internals']['cur_reports']['report_directory']
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
        self.minDate = ''
        self.maxDate = ''

        try:
            self.client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('athena', region_name=self.cur_region)
        except Exception as e:
            self.appConfig.console.print(f'\n[red]Unable to establish boto session for Support. \n{e}[/red]')
            sys.exit()

    @staticmethod
    def name():
        return "cur"

    def long_name(self):
        return "Cost & Usage Report"

    def auth(self):
        """CUR report provider authentication logic"""
        # Add any specific authentication logic here if needed
        pass

    def setup(self, run_validation=False):
        """Setup instructions for CUR report type"""

        #super().setup()
        # Add any CUR-specific setup instructions here
        """Setup instructions for CUR report type"""
        # retrieve Athena database information from customer configuration
        try:
            self.cur_s3_bucket = self.appConfig.config['cur_s3_bucket']
            self.cur_db = self.appConfig.arguments_parsed.cur_db if (hasattr(self.appConfig.arguments_parsed, 'cur_db') and self.appConfig.arguments_parsed.cur_db is not None) else self.appConfig.config['cur_db']
            self.cur_table = self.appConfig.arguments_parsed.cur_table if (hasattr(self.appConfig.arguments_parsed, 'cur_table') and self.appConfig.arguments_parsed.cur_db is not None) else self.appConfig.config['cur_table']
            self.cur_region = self.appConfig.arguments_parsed.cur_region if (hasattr(self.appConfig.arguments_parsed, 'cur_region')  and self.appConfig.arguments_parsed.cur_region is not None) else self.appConfig.config['cur_region']
        except KeyError as e:
            self.logger.error(f'MissingCurConfigurationParameterException: Missing CUR parameter in report requests: {str(e)}')
            raise

        #Athena table name
        self.fqdb_name = f'{self.cur_db}.{self.cur_table}'
        self.logger.info(f'Setting {self.name()} report table_name to: {self.fqdb_name}')

        #Athena database connection
        self._cursor = self._make_cursor()

        self.logger.info(f'setting query parameters for {self.name()}')
        self.set_query_parameters() #create parameters to pass to each query

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

    def execute_report(self, report_object, query, display=True, cached=False):
        def run_query( report_object, display, report_name):
            try:

                payer_str = "bill_payer_account_id='"+self.appConfig.config['aws_cow_account']+"' AND "
                account_str = "line_item_usage_account_id LIKE '%' AND " #+self.appConfig.config['aws_cow_account']
                region_str = "product_region='"+self.appConfig.selected_regions[0]+"' AND "

                if self.minDate == '' or self.maxDate == '':
                    # Get the months_back parameter if provided
                    months_back = 0
                    if hasattr(self.appConfig.arguments_parsed, 'cur_month_date_minus_x'):
                        months_back = self.appConfig.arguments_parsed.cur_month_date_minus_x
                    self.minDate, self.maxDate = report_object.GetMinAndMaxDateFromCurTable(self.client, self.fqdb_name, months_back=months_back)
                if self.maxDate == 'N/A':                 
                    max_date = "NOW()"
                else:
                    max_date = self.maxDate
                CurQuery = report_object.sql( self.fqdb_name, payer_str, account_str, region_str, max_date)

                v_SQL=CurQuery.get("query", "")

                if report_object.service_name() == self.long_name():
                    report_object.addCurReport( self.client , v_SQL, 
                        report_object.get_range_categories() , 
                        report_object.get_range_values(),
                        report_object.get_list_cols_currency(),
                        report_object.get_group_by(), display, report_name)

                self.logger.info(f'Running CUR query: {report_name} ')
            except Exception as e:
                self.logger.error('Exception occured when during execution of CUR query')
                self.logger.exception(e)
                self.appConfig.console.print(f'\n[red underline]ERROR: Exception occured when during execution of CUR query >>> {e}')
                sys.exit()

        report_name = report_object.name()
        
        display_msg = f'[green]Running Cost & Usage Report: {report_name} / {self.appConfig.selected_regions}[/green]'
        
        if cached:
            for _ in track(range(1), description=display_msg + ' [yellow]CACHED'):
                pass

        else:
            run_query( report_object, display, report_name)

    def fetch_data(self, 
        reports_in_progress:list, 
        additional_input_data=None, 
        expiration_days=None, 
        type=None,
        display=True,
        cow_execution_type=None):

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

                if cache_status is False:
                    self.delete_cache_file(report_name, self.accounts, self.regions, self.customer, additional_input_data)

                if not self.check_cached_data(report_name, self.accounts, self.regions, self.customer, additional_input_data, expiration_days) or cache_status == False:
                    cache_status = q.get_caching_status()

                if cache_status ==False:
                    self.delete_cache_file(report_name, self.accounts, self.regions, self.customer, additional_input_data)

                if not self.check_cached_data(report_name, self.accounts, self.regions, self.customer, additional_input_data, expiration_days) or cache_status == False:
                    
                    q.execution_state = True
                    self.logger.info(f'CUR report query state reported : {q.name()} query id: {q.query_id}')
                    
                    q.dataframe = []
                    q.output = []
                    # check if report_result is member of q
                    if hasattr(q, 'report_result'):
                        if len(q.report_result):
                            # if  q.report_result dict has member Data
                            if 'Data' in q.report_result[0]:
                                q.dataframe = q.report_result[0]['Data']
                                # test if q.dataframe is not equal to []
                                if len(q.dataframe) > 0:
                                    q.output = q.dataframe.to_json()
                                else:
                                    q.output = '[]'
                    
                    #dump CUR data to cache
                    #self.write_cache_data(report_name, report, accounts, regions, customer, additional_input_data)
                    q.post_processing()

                    if type == 'base' and q.report_dependency_list != []:
                        q.dataframe = q.create_report_data(q.dataframe) #store data in create_report_data for dependency use
                        self.succeeded_queries.append(q)
                        self.completed_reports.append(q)
                    else:
                        self.succeeded_queries.append(q)
                        self.completed_reports.append(q)

                    self.logger.info(f'Data CUR {q.name()} not found in cache.')
                else:
                    #pull report output data from cache
                    self.logger.info(f'CUR Report -  {q.name()}: Fetching report data from cache')
                    cache_file_name = self.get_cache_file_name(report_name, self.accounts, self.regions, self.customer, additional_input_data)
                    self.logger.info(f'Decrypting cache file {cache_file_name} for CUR Report')
                    #self.appConfig.encryption.decrypt_file(cache_file_name)
                    input_file = open(cache_file_name,'r')
                    raw_data=input_file.read()
                    input_file.close()
                    #self.logger.info(f'Encrypting cache file {cache_file_name} for CUR Report')
                    #if self.verify_cache_file_name(cache_file_name):
                    #    self.appConfig.encryption.encrypt_file(cache_file_name)
                    report.output=json.loads(raw_data) #loads raw data into self.output = for report
                    q.dataframe = pd.read_json(report.output)
                    q.post_processing()

                    if type == 'base' and q.report_dependency_list != []:
                        q.dataframe = q.create_report_data(q.dataframe)
                        self.succeeded_queries.append(q)
                        self.completed_reports.append(q)
                    else:
                        self.succeeded_queries.append(q)
                        self.completed_reports.append(q)

    def _make_cursor(self):
        """Create an Athena cursor"""
        return self.client

    def show_columns(self) -> list:
        """Show columns in the CUR table"""
        query = f"SHOW COLUMNS IN {self.fqdb_name}"
        result = self.fetch_data(query)
        return [row['Data'][0]['VarCharValue'] for row in result['ResultSet']['Rows'][1:]]

    def show_partitions(self) -> list:
        """Show partitions in the CUR table"""
        query = f"SHOW PARTITIONS {self.fqdb_name}"
        result = self.fetch_data(query)
        return [row['Data'][0]['VarCharValue'] for row in result['ResultSet']['Rows']]

    def set_query_parameters(self) -> None:
        """Set query parameters for CUR reports"""
        self.query_parameters = {
            'database': self.cur_db,
            'table': self.cur_table,
            'output_location': f'{self.cur_s3_bucket}/athena_query_results/'
        }

    def calculate_savings(self):
        """Calculate savings based on CUR data"""
        # This method should be implemented based on specific savings calculation logic
        pass

    def generate_query(self, report_object):
        """Generate the SQL query for the report"""
        group_by = report_object.get_group_by()
        metrics = report_object.get_metrics()
        filters = report_object.get_filters()
        
        select_clause = ", ".join(group_by + metrics)
        where_clause = " AND ".join([f"{k} = '{v}'" for k, v in filters.items()]) if filters else "1=1"
        group_by_clause = ", ".join(group_by)
        
        query = f"""
        SELECT {select_clause}
        FROM {self.fqdb_name}
        WHERE {where_clause}
        GROUP BY {group_by_clause}
        ORDER BY {group_by[0]}
        """
        return query

    def start_query_execution(self, query):
        """Start the Athena query execution"""
        response = self.client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={
                'Database': self.cur_db
            },
            ResultConfiguration={
                'OutputLocation': f'{self.cur_s3_bucket}/athena_query_results/'
            }
        )
        return response['QueryExecutionId']

    def get_query_results(self, execution_id):
        """Get the results of the Athena query"""
        while True:
            response = self.client.get_query_execution(QueryExecutionId=execution_id)
            state = response['QueryExecution']['Status']['State']
            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            time.sleep(1)

        if state == 'SUCCEEDED':
            return self.client.get_query_results(QueryExecutionId=execution_id)
        else:
            raise Exception(f"Query execution failed: {response['QueryExecution']['Status']['StateChangeReason']}")

    def display_results(self, result, report_object):
        """Display the results of the report"""
        columns = [col['Label'] for col in result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        rows = result['ResultSet']['Rows'][1:]  # Skip the header row
        
        print(f"\nResults for {report_object.name()}:")
        print("-" * 80)
        print(" | ".join(columns))
        print("-" * 80)
        
        for row in rows:
            print(" | ".join([data['VarCharValue'] for data in row['Data']]))

    def get_cached_data(self, report_object):
        """Retrieve cached data for the report"""
        cache_key = f"{self.name()}_{report_object.name()}"
        cached_data = self.appConfig.cache.get(cache_key)
        
        if cached_data:
            self.logger.info(f"Retrieved cached data for {report_object.name()}")
            return cached_data
        else:
            self.logger.info(f"No cached data found for {report_object.name()}")
            return None

    def cache_data(self, report_object, data):
        """Cache the report data"""
        cache_key = f"{self.name()}_{report_object.name()}"
        self.appConfig.cache.set(cache_key, data, expire=self.appConfig.config.get('cache_expiration', 3600))
        self.logger.info(f"Cached data for {report_object.name()}")