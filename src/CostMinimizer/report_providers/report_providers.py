# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import logging, importlib, os
import datetime
import json
import re
import hashlib
from abc import ABC
from pathlib import Path
import ast
import datetime
import logging
from abc import ABC, abstractmethod
import sys

from ..config.config import Config


class InvalidReportInputException(Exception):
    pass


class MissingCurConfigurationParameterException(Exception):
    pass


class MissingReportsDirectoryException(Exception):
    pass

class UnableToOpenMappingsFile(Exception):
    pass


class ReportProviderBase(ABC):

    '''
    ReportProvider base class to be inherited by each report provider.
    Provides abstract methods for report provider identification, authentication,
    setup and the exectution of the report

    name() - each report provider should return an identification string
    auth() - each report provider needs to provide authentication logic
    setup() - method to run any necessary setup before the exectution of reports by provider
    run() - execute reports under this report provider
    '''
    def __init__(self, appConfig) -> None:
        
        self.logger = logging.getLogger(__name__)
        self.appConfig = Config()

        self.report_input = None
        self.report_directory = None #MUST OVERIDE IN REPORT PROVIDER
        self.module_path =  self.appConfig.internals['internals']['reports']['reports_module_path']
        self.cache_dir = self.appConfig.app_path / self.appConfig.internals['internals']['reports']['cache_directory']
        self.expire_file_cache = self.appConfig.internals['internals']['reports']['expire_file_cache']
        self.account_discovery = None
        self.dependency_run = None
        self.dependent_report = None

        self.parent_reports_in_progress =[]
        self.dependent_reports_in_progress = []


        self.excluded_regions = []

        #initialize holders of reports
        self.enabled_reports = []
        self.available_reports = []
        self.approved_reports = []
        
        '''curated report output - after we have reduced and calculated pricing/savings in columns'''
        self.curated_report_output = None

        self.writer = None

        self.enrollment_status = True

    def name(self):
        '''return name of report provider''' 
        pass
    
    def auth(self):
        """
        Perform authentication for the report provider.
        """
        '''report provider authentication logic'''
        pass

    def setup(self):
        """
        Set up the report provider.
        """
        '''any setup necessary before execution of reports'''
        pass

    def _set_report_object(self):
        """
        Set the report object for the provider.
        """
        '''return report object'''
        pass

    @abstractmethod
    def run_additional_logic_for_provider(self, report_object, additional_input_data=None):
        """
        Run additional logic specific to the provider.
        """
        '''run any additional logic for provider when executing the run method'''
        pass

    def run(self):
        """
        Run the report provider.
        """
        '''execute reports'''
        pass

    def mandatory_reports(self, type='base'):
        """
        Get the list of mandatory reports.
        
        :param type: Type of mandatory reports to retrieve
        :return: List of mandatory reports
        """
        '''mandatory report logic'''
        pass
    
    def provider_run(self, additional_input_data, display):
        """
        Run the provider with additional input data.
        
        :param additional_input_data: Additional input data for the provider
        :param display: Display flag
        """
        '''execute provider run'''
        # run reports
        for report in self.reports:
            
            # instantiate report/query object
            report_object = self._set_report_object(report)
            report_object.setup()

            if hasattr(self.appConfig, 'using_tags') and self.appConfig.using_tags is True:
                report_object.set_tag_dependencies()

            report_name = report_object.name()

            cache_status = 'report_object.get_caching_status()'

            '''get params from db, store in app, send to method'''
            params = self.appConfig.database.get_report_parameters(report_object.common_name())

            if params != []:
                report_object.set_report_parameters(params)

            if report_object.precondition_report() and additional_input_data != 'preconditioned':
                self.logger.info(f'removing {self.name()} preconditioning report: {report_name}')
                self.get_approved_reports().remove(report_object.name())
                additional_input_data = None
                continue
            elif report_object.precondition_report() and additional_input_data == 'preconditioned':
                additional_input_data = None

            # if forced disabled
            if report_object.disable_report():
                self.logger.info(f'{self.name()} removing disabled report: {report_name}')
                self.get_approved_reports().remove(report_object.name())
                continue

            self.execute_dependent_reports(report_object, self.appConfig.cow_execution_type)

            self.logger.info(f'Running report {report_name}')

            self.run_additional_logic_for_provider(report_object, additional_input_data)
            self.accounts, self.regions, self.customer = self.set_report_request_for_run()

            self.logger.info(f'{report_name}: Requested in {self.appConfig.cow_execution_type} mode.')
            self.logger.info(f'{report_name}: Running against account #{self.accounts} and region {self.regions}.')
            
            if not self.check_cached_data(report_name, self.accounts, self.regions, self.customer, self.additional_input_data, self.expiration_days):
                #if report is not cached, execute report
                self.logger.info(f'{report_name}: Report not found in CACHE')

                self.execute_report(report_object, display)

            else: 
                #if report is cached, and we are running in sync mode, skip report
                self.logger.info(f'{report_name}: Report found in CACHE')

                report_object.execution_ids = {report_object.name(): 'CACHED'}
                
                self.execute_report(report_object, display, cached=False)

            self.list_reports_results.append(report_object.report_result)


            #track all reports in progress
            self.reports_in_progress.append(report_object)

            #write execution id to database
            #if not self.account_discovery and self.appConfig.k2_account_validation_complete:
            if not self.account_discovery and report_object.write_to_db() == True:
                self.write_execution_id_to_database(report_object.name(), report_object.execution_ids)

    def import_reports(self, provided_report_metadata=None) -> list:
        """
        Import reports based on provided metadata.

        :param provided_report_metadata: Metadata for the reports to import
        :return: List of imported reports
        """
        '''import and return a list of all approved report classes'''
        
        #import reports may be used with report metadata provided from other sources
        if provided_report_metadata:
            report_metadata = provided_report_metadata
        else:
            report_metadata = self._set_approved_report_names(self.get_approved_reports()) # holds mapping of report name to report class name
        
        reports = []
        for report_name,report_class in report_metadata.items():
            module_path = f'{self.module_path}.{self.name()}_reports.reports.{report_name}'
            module = importlib.import_module(module_path)
        
            report_class = getattr(module, report_class)
            reports.append(report_class)
        
        #We don't log all found reports with provided metadata
        if not provided_report_metadata:
            self.log_found_reports()

        return reports

    def _set_enabled_reports(self) -> list:
        """
        Set the list of enabled reports.

        :return: List of enabled reports
        """
        '''Return all enabled reports as defined in the report_request'''
        enabled_reports = []
        for report, report_enabled in self.appConfig.reports.get_all_reports().items():
            report_name = report.split('.')[0]
            report_type = report.split('.')[1]

            if report_type == self.name() and report_enabled is True:
                enabled_reports.append(report_name)

        return enabled_reports
    
    def _set_available_reports(self, return_available_report_objects=False) -> list:
        """
        Set the list of available reports.

        :param return_available_report_objects: Flag to return report objects
        :return: List of available reports
        """
        '''
        Return list of reports found in the report directory
        
        parameter: return_available_report_objects - set to True will return the report objects
        '''
        try:
            report_directory = self.report_directory
        except:
            self.logger.error(f'Mssing configuration parameter in cow internals {self.name()}_reports section: report_directory')
            raise MissingCurConfigurationParameterException(f'Missing configuration parameter in cow internals {self.name()}_reports section: report_directory')

        if report_directory is None:
            self.logger.error(f'Provider {self.name()}_reports is missing a variable overrider for self.report_directory')
            raise MissingCurConfigurationParameterException(f'Provider {self.name()}_reports is missing a variable overrider for self.report_directory')
        
        try:
            report_files = [f for f in report_directory.glob('*.py') if f.is_file()]
        except FileNotFoundError as e:
            self.logger.error(f'[Error] Unable to locate reports directory for {self.name()}_reports.  Check if directory exists: {report_directory}')
            raise MissingReportsDirectoryException(f'[Error] Unable to locate reports directory for {self.name()}_reports.  Check if directory exists: {report_directory}')
            
        all_reports_found = []
        for f in report_files:
            if f.name == '__init__.py':
                continue
            all_reports_found.append(f.stem)
        
        if return_available_report_objects:
            #Get report file names and their class names
            report_metadata = self._set_approved_report_names(all_reports_found)
            
            #import and instantiate reports 
            imported_reports = self.import_reports(report_metadata)

            return imported_reports

        return all_reports_found    
    
    def _set_approved_reports(self) -> list:
        """
        Set the list of approved reports.

        :return: List of approved reports
        """
        '''return a list of reports that are both enabled and available'''
        approved_reports = [ report for report in self.get_enabled_reports() if report in self.get_available_reports() ]
        
        return approved_reports
    
    def _set_approved_report_names(self, approved_reports) -> dict:
        """
        Set the names of approved reports.

        :param approved_reports: List of approved reports
        :return: Dictionary of approved report names
        """
        '''return a dictionary of approved report names and their accompaning class names'''
        report_names_and_classes = {}
        for report in approved_reports:
            class_name = [ _.title() for _ in report.split('_') ]
            report_names_and_classes[report] = ''.join(class_name)

        return report_names_and_classes

    def set_display(self) -> bool:
        """
        Set the display flag for the report provider.

        :return: Boolean indicating whether to display
        """
        ''' set display for reports'''
        if self.appConfig.mode == 'module':
            return False
        
        return True

    def set_expiration_days(self, expiration_days) -> int:
        """
        Set the expiration days for cached data.

        :param expiration_days: Number of days until expiration
        :return: Set expiration days
        """
        '''return expiration days from configuration file'''
        if expiration_days is None:
            expiration_days = 8

        return expiration_days

    def set_report_request_for_run(self):
        """
        Set the report request for running the provider.
        """
        '''return accounts, regions and customers for report run'''
        account = 'default'
        region = 'default'
        customer = 'default'

        try:
            # retreive account number from boto3 sts current session
            account = self.appConfig.auth_manager.aws_cow_account_boto_session.client('sts').get_caller_identity()['Account']

            # Set default region if selected_regions is None
            if hasattr(self.appConfig, 'selected_regions') and self.appConfig.selected_regions:
                region = self.appConfig.selected_regions
            else:
                # Use default region from config
                region = self.appConfig.default_selected_region if hasattr(self.appConfig, 'default_selected_region') else 'us-east-1'
                # Set the selected_regions attribute to avoid None issues later
                self.appConfig.selected_regions = [region]
        except Exception as e:
            msg = f'Error: unable to retreive STS information. Check your credentials.  Get new credentials before starting the program.'
            self.logger.exception(msg)
            self.appConfig.console.print(f'\n[red underline]{msg}')
            sys.exit(0)

        return account, region, customer

    def execute_dependent_reports(self, report_object, cow_execution_type) -> None:
        """
        Execute dependent reports for the given report object.

        :param report_object: The report object to check for dependencies
        :param cow_execution_type: The execution type (sync/async)
        """
        '''execute dependent reports'''
        if report_object.report_dependency_list != []:
            self.get_dependency_reports(report_object, cow_execution_type)
            #self.get_dependency_reports(report_object, 'sync')

    def _validate_report_input(self, report_input) -> dict:
        """
        Validate the report input data.

        :param report_input: The input data for the report
        :return: Validated report input as a dictionary
        """

        '''validate report input contains enabled reports'''
        if 'enabled_reports' in report_input.keys():
            return report_input
        else:
            raise InvalidReportInputException(f'Report_input not provided in valid format for {self.name()}: {report_input}')

    def expire_cached_data(self, api_name, cache_file ,expiration_days):
        """
        Expire cached data based on the expiration days.

        :param api_name: Name of the API
        :param cache_file: Path to the cache file
        :param expiration_days: Number of days after which the cache expires
        """
        '''expire cached data based on configurable expiration param in internals yaml file'''
        if self.check_for_cache_file(cache_file):
            #parse cache file name for creation timestamp
            cache_file_name_with_timestamp = self.get_full_cache_file_name(cache_file)
            
            timestring = self.get_timestamp_from_cachefile(cache_file_name_with_timestamp)
            
            try:
                epoch_time = float(timestring)
            except:
                self.logger.error(f'Error in expiring cache file: {cache_file_name_with_timestamp}.')
                if self.appConfig.mode == 'cli':
                    print(f'Error in expiring cache file: {cache_file_name_with_timestamp}.')
                else:
                    self.appConfig.alerts['cache_file_error'] = f'Error in expiring cache file: {cache_file_name_with_timestamp}.'
                
                return 
            
            cache_file_absolute_path = self.cache_dir / cache_file_name_with_timestamp
            
            current_time = datetime.datetime.now().timestamp()
            time_difference = current_time - epoch_time

            expiration_seconds = self.set_expiration_seconds(expiration_days)

            if time_difference >= expiration_seconds:
                if cache_file_absolute_path.is_file():
                    os.remove(cache_file_absolute_path)
                    self.logger.info(f'Data in cache older than {self.expire_file_cache} days. Expired old cache data for {api_name}.')
                else:
                    self.logger.info(f'Unable to expire cache file {cache_file_absolute_path}.')

    def write_cache_data(self, api_name, report_output, accounts, regions, customer, additional_input_data=None):
        """
        Write cache data to a file.

        :param api_name: Name of the API
        :param report_output: Output data to be cached
        :param accounts: List of accounts
        :param regions: List of regions
        :param customer: Customer information
        :param additional_input_data: Any additional input data
        """
        ''' write data from report into cache'''
        hash_for_file = self.generate_cache_hash(api_name, accounts, regions, customer, additional_input_data)
        timestamp_for_file = datetime.datetime.now().timestamp()
        
        #dump data to cache
        cache_file = str(self.cache_dir) + "/" + api_name + '_output_' + hash_for_file + '_time_' + str(timestamp_for_file) + '.json'
        output_file = open(cache_file,'a')
        
        if isinstance(report_output, list): 
            output_file.write(json.dumps(report_output)) #if we pass in a list of items to cache
        else: 
            output_file.write(json.dumps(report_output.output)) #if we pass in report object
        output_file.close()

        #encrypt cache file
        #self.appConfig.encryption.encrypt_file(cache_file)

    def get_cache_file_name(self, api_name, accounts, regions, customer, additional_input_data=None) -> str:
        """
        Generate a cache file name based on the input parameters.

        :param api_name: Name of the API
        :param accounts: List of accounts
        :param regions: List of regions
        :param customer: Customer information
        :param additional_input_data: Any additional input data
        :return: Generated cache file name
        """
        '''get cache file name (absolute path)'''
        hash_for_file = self.generate_cache_hash(api_name, accounts, regions, customer, additional_input_data)
        cache_file_name_with_timestamp = f"{api_name}_output_{hash_for_file}_time_*.json"
        
        return self.cache_dir / self.get_full_cache_file_name(cache_file_name_with_timestamp)
    
    def generate_cache_hash(self, api_name, accounts, regions, customer, additional_input_data) -> str:
        """
        Generate a hash for the cache based on the input parameters.

        :param api_name: Name of the API
        :param accounts: List of accounts
        :param regions: List of regions
        :param customer: Customer information
        :param additional_input_data: Any additional input data
        :return: Generated hash string
        """
        '''
        generate a unique hash when given the input of api name, accounts, regions, customer
        
        we need a hash to determine if the cache file is for the same report request
        '''

        m = hashlib.sha256()
        a = ''.join(accounts)
        r = ''.join(regions)
        
        if additional_input_data is None or len(additional_input_data) == 0:
            hash_string = f"{customer}.{api_name}.{r}.{a}"
        else:
            if isinstance(additional_input_data, dict):
                for data in additional_input_data.values():
                    #there should only be one item in the dict
                    hash_string = f"{customer}.{api_name}.{r}.{a}.{data}"
            if isinstance(additional_input_data, list):
                #there should only be one item in the dict
                hash_string = f"{customer}.{api_name}.{r}.{a}.{additional_input_data[0]}"

        m.update(bytes(hash_string, encoding='utf-8'))

        return m.hexdigest()

    def get_full_cache_file_name(self, cache_file) -> str:
        """
        Get the full path of the cache file.

        :param cache_file: Base name of the cache file
        :return: Full path of the cache file
        """
        '''retrieve full cache file name with timestamp'''
        matching_files = list(self.cache_dir.glob(cache_file))

        if len(matching_files) > 0:
            return matching_files[0].name
        else:
            return None
        
    def set_expiration_seconds(self, expiration_days=8):
        """
        Set the expiration time in seconds based on the number of days.

        :param expiration_days: Number of days until expiration (default is 8)
        :return: Expiration time in seconds
        """
        '''set expiration seconds'''
        return (24 * 60 * 60) * expiration_days
        
    def get_timestamp_from_cachefile(self, cache_file_with_timestamp) -> str:
        """
        Extract the timestamp from a cache file name.

        :param cache_file_with_timestamp: Cache file name containing a timestamp
        :return: Extracted timestamp as a string
        """
        '''get timestamp from cache file'''
        pattern = r'_time_(.*?)\.json' 
        match = re.search(pattern, cache_file_with_timestamp)
        if match:
            return match.group(1)
        else:
            return ''
    
    def check_for_cache_file(self, cache_file) -> bool:
        """
        Check if a cache file exists.

        :param cache_file: Name of the cache file to check
        :return: True if the cache file exists, False otherwise
        """
        '''check if cache file exists for report in cache directory'''
        matching_files = self.cache_dir.glob(cache_file)

        if any(matching_files):
            return True
        else:
            return False
    
    def verify_cache_file_name(self, cache_file:Path) -> bool:
        """
        Verify if the cache file name is valid.

        :param cache_file: Path object representing the cache file
        :return: True if the cache file name is valid, False otherwise
        """

        if "_output_" in cache_file.name and cache_file.suffix == '.json':
            return True
        else:
            return False
    
    def check_cached_data(self, api_name, accounts, regions, customer, additional_input_data=None, expiration_days=1) -> bool:
        """
        Check if valid cached data exists for the given parameters.

        :param api_name: Name of the API
        :param accounts: List of accounts
        :param regions: List of regions
        :param customer: Customer information
        :param additional_input_data: Any additional input data
        :param expiration_days: Number of days after which the cache expires
        :return: True if valid cached data exists, False otherwise
        """
        '''check if cache file exists for report in cache directory'''

        hash_for_file = self.generate_cache_hash(api_name, accounts, regions, customer, additional_input_data)
        cache_file = f"{api_name}_output_{hash_for_file}_time_*.json"
        
        #check if cache dir exists; if not create
        if not self.cache_dir.is_dir():
            os.mkdir(self.cache_dir)

        self.expire_cached_data(api_name, cache_file, expiration_days)
        
        if self.check_for_cache_file(cache_file):
            #Did not find cached data
            return True
        else:
            #Found cached data
            return False
        
    def delete_cache_file(self, api_name, accounts, regions, customer, additional_input_data=None):
        """
        Delete the cache file for the given parameters.

        :param api_name: Name of the API
        :param accounts: List of accounts
        :param regions: List of regions
        :param customer: Customer information
        :param additional_input_data: Any additional input data
        """
        '''delete cache file for reports with disabled caching'''
        hash_for_file = self.generate_cache_hash(api_name, accounts, regions, customer, additional_input_data)
        cache_file = f"{api_name}_output_{hash_for_file}_time_*.json"
        cache_file_name_with_timestamp = self.get_full_cache_file_name(cache_file)
        if cache_file_name_with_timestamp is None:
            return
        cache_file_absolute_path = self.cache_dir / cache_file_name_with_timestamp
        if cache_file_absolute_path.is_file():
            os.remove(cache_file_absolute_path)
            self.logger.info(f'Report caching disabled. Deleted cache file {cache_file_name_with_timestamp}')
        else:
            self.logger.info(f'Unable to delete cache file {cache_file_name_with_timestamp}.')
        
    def get_dependency_reports(self, report_object, cow_execution_type):
        """
        Get and execute dependency reports for the given report object.

        :param report_object: The report object to check for dependencies
        :param cow_execution_type: The execution type (sync/async)
        """
        '''
        obtain dependency information from all reports
        run each dependency against report request 
        attach dependency output data to report as dependency_data list
        '''
        
        for report in report_object.report_dependency_list:

            reports, send_report={},{}
            
            send_report[report['dependency_report_name']] = report['dependency_report_class']
            provider = report['dependency_report_provider'] 
            module_path = self.module_path + '.' + provider + '_reports' + '.' + provider
            module = importlib.import_module(module_path)

            provider_class = getattr(module, provider.title() + 'Reports')

            dependency_report = provider_class(self.appConfig, reports, dependency_run=True, dependent_report=f'{report_object.name()}.{report_object.report_provider()}')
            dependency_report.auth()
            dependency_report.setup(run_validation=True, dependency_status = True)
            
            report_list = dependency_report.import_reports(send_report)

            dependency_report.run(report_list, display=False, cow_execution_type=cow_execution_type)
            reports_in_progress = dependency_report.reports_in_progress
            
            if self.appConfig.cow_execution_type == 'sync':
                dependency_report.fetch_data(dependency_report.reports_in_progress,
                                            additional_input_data=None, 
                                            expiration_days=None, 
                                            type=None,
                                            display=True,
                                            cow_execution_type=cow_execution_type)
                
                report_object.dependency_data[report['dependency_report_name']] = dependency_report.get_data()
    
    def get_enabled_reports(self) -> list:
        """
        Get the list of enabled reports.

        :return: List of enabled reports
        """
        self.enabled_reports = self._set_enabled_reports()
        return self.enabled_reports

    def get_available_reports(self, return_available_report_objects=False) -> list:
        """
        Get the list of available reports.

        :param return_available_report_objects: If True, return report objects instead of names
        :return: List of available reports
        """
        '''return all available reports under configured report directory'''
        self.available_reports = self._set_available_reports(return_available_report_objects)
        return self.available_reports

    def get_approved_reports(self):
        """
        Get the list of approved reports.

        :return: List of approved reports
        """
        self.approved_reports = self._set_approved_reports()
        return self.approved_reports

    def get_completed_reports_from_provider(self) -> list:
        """
        Get the list of completed reports from the provider.

        :return: List of completed reports
        """
        '''return list of completed reports'''
        return self.completed_reports, self.failed_reports

    def log_found_reports(self):
        """
        Log the found reports.
        """
        self.logger.info(f'{self.name()} report - enabled reports: {self.enabled_reports}')
        self.logger.info(f'{self.name()} report - available reports found: {self.available_reports}')
        self.logger.info(f'{self.name()} report - approved reports: {self.approved_reports}')
    

    def write_execution_id_to_database(self, report_name, execution_id):
        """
        Write the execution ID to the database for the given report.

        :param report_name: Name of the report
        :param execution_id: Execution ID to be written
        """
        '''write execution id to database'''
        hash = hashlib.md5(self.appConfig.report_time.encode('utf-8')).hexdigest()
        #customer_id = self.appConfig.customers.get_customer_data(self.appConfig.customers.selected_customer)['id']
        try:
            comment = self.appConfig.tag
        except:
            comment = ''

        if comment is False:
            comment = ''

        dependent_report = self.dependent_report if self.dependent_report else ''
        request = { 'report_id': hash, 'report_name': report_name,  'report_provider': self.name(), 'report_exec_id': report_name, 'parent_report': dependent_report, 'start_time': self.appConfig.report_time, 'status': '', 'comment': comment, 'cx_id_id': 'default_customer_id','using_tags': self.appConfig.using_tags}
      
        self.appConfig.database.insert_record(request, 'cow_cowreporthistory')


class ReportBase(ABC):

    '''
    Report base class to be inherited by each report.
    Provides abstract methods for report identification, description, calculation

    name() - each report provider should return an identification string
    auth() - each report provider needs to provide authentication logic
    setup() - method to run any necessary setup before the exectution of reports by provider
    run() - execute reports under this report provider
    '''


    def __init__(self, appConfig) -> None:
        self.recommendation = None
        self.failed_execution = [] #holds report objects which have failures
        self.failed_execution_details = {} #details of failed execution
        self.failed_report_logs = {} #hold logs for failed executions
        self.joined_report =False
        self.report_output_phase= False
        self.execution_ids = {} #holds execution ids for each report

        ''' 
        execution status: False if not finished; True if finished
        We want it True by default in case the report is pulled from cache
        '''
        self.execution_state = True 

    def name(self):
        '''
        return report name
        report names should not be > 31 chars (openxls limitation on writing sheet names)
        '''
        pass
    
    def common_name(self):
        '''
        return report common name
        a more display friendly name for use in i.e. menu
        '''  
        pass

    def description(self):
        '''return report description'''
        pass

    def pricing_api_name(self):
        '''
        provide the service code for the pricing api
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/pricing.html
        i.e. 'AmazonEC2'
        
        Use None if pricing api is not required for the report
         '''
        pass

    def pricing_api_filter(self) -> list:
        '''
        privide example of the filtes needed to filter the pricing result 
        i.e. ['ebs_type', 'ebs_iops']
        
        Use empty list if pricing api is not required for the report 
        '''
        pass

    def report_type(self) -> str:
        '''
        returns a string representing the report type

        There are two report types:
        'processed' - represents a report which returns a savings target
        'raw' - represents a report which is purely informational, unprocessed data
        '''
        pass

    def service_name(self) -> str:
        '''
        returns which service the report is tied to.  as a standard we should use the same service 
        name (all lowercase) as line_item_product_code and product_product_family in CUR data

        example report: select DISTINCT(line_item_product_code), product_product_family from csaws_cur

        i.e. for EBS:
        amazonec2_storage

        if line_item_product_code returns multiple services such as when working with networking, use a general term
        such as 'network'

        i.e. :
        network_data_transfer
        '''
        pass

    def report_provider(self) -> str:
        '''
        return report provider name (i.e. cur, k2 etc...)
        
        Note - We could discover this programmatically based on 
        the report_directory name in _set_available_reports().  Not
        sure if that's overkill
        
        '''

    def disable_report(self) -> bool:
        '''
        Ability for development team to disable a particular report and 
        override the user selection

        return True or False
        '''

    def precondition_report(self) -> bool:
        '''
        Set to true if this report is meant to run as a precondition report only

        return True or False

        Default set to False
        '''

        return False

    def require_user_provided_region(self) -> bool:
        '''
        Certain reports such as trusted advisor typically run in us-east-1
        other reports require regions to be selected by the user
        '''
        return False

    def calculate_savings(self):
        '''do the work to calculate the savings'''
        pass

    def get_estimated_savings(self) -> float:
        '''return the estimated savings for the report'''
        pass

    def display_in_menu(self) -> bool:
        '''Display the report in the menu'''
        return True

    def long_description(self) -> str:
        '''return long description of report'''
        return ''
    
    def domain_name(self) -> str:
        '''return domain name of report'''
        return ''

    def get_report(self) -> dict:
        '''
        output report 
        
        report needs to hand back a dict:
        
        { 
            data: pd.DataFrame
            savings: int
        }

        data: pandas dataFrame of rows and columns relevant to the report
        savings: if the report is processed it needs to hand back the identified savings
        '''
        
        return { 
            'data': self.get_report_dataframe(),
            'savings': self.get_estimated_savings()
        }
    
    def get_recommendation(self) -> str:
        ''' return recommendation for the report'''

        return self.recommendation

    def set_recommendation(self) -> None:
        ''' 
        Set a dynamice recommendation for the report.  This 
        method should be overwritten by the child reports which 
        need to deliver a recommendation based on a condition.
        '''

        return None

    def enable_comparison(self) -> bool:
        '''Include in report comparison'''
        return False
    
    def get_mappings(self) -> dict:
        '''
        Retrive mappings file

        Mappings files contains various mappings which may not be obtainable through data such as old gen instances to new gen instances
        
        Mappings files should be located in 'helpers' folders under a report providers report dir.  They should be named as the <report_name>_mappings.json
        '''
        mappings_file = Path(__file__).parent / f'{self.report_provider()}_reports' / 'reports' / 'helpers' / f'{self.name()}_mappings.json'

        try:
            if mappings_file.is_file():
                with open(str(mappings_file)) as f:
                    data = json.load(f)
        except:
            msg = f"Unable to open mappings file {mappings_file} for report {self.name()}."
            raise UnableToOpenMappingsFile(msg)
             
        return data
    
    def get_report_html_link(self) -> str:
        '''link to documentation for report'''
        return '#'
  
    def set_report_parameters(self) -> None:
        '''
        set report parameters
        used to set report values
        '''
        pass
    def get_report_parameters(self) -> dict:
        '''
        return report parameters
        used to customize report values
        '''
        return {}
    
    def get_parameter_list(self,params) -> dict:
        '''return a dict with a list of user-defined report paramters from the DB'''
        return ast.literal_eval(params[0][0])
		
    def is_report_configurable(self)-> bool:
        return False
    
    def supports_user_tags(self) -> bool:
        return False
    
    def write_to_db(self) -> bool:
        '''Write exections to DB. Override to false in the report definition to skip this'''
        return True
    
    def set_tag_dependencies(self) -> None:
        '''Override to set a dependency report in a Internal script when tags are being used. 
        Examples below on how to specify using tags and set a dependency report in your k2 or cur report definition
        
        self.using_tags = True
		self.report_dependency_list=[{'dependency_report_provider': 'k2','dependency_report_name':'cloudtrail_management','dependency_report_class':'CloudtrailManagement'}]
		
        '''
        pass

    def normalize_tag_key(self,tag_name) -> str:
        '''Convert the tag key into an Athena friendly configuration'''

        #replace non-alpha with underscore
        if tag_name.isalnum() is False:
            for char in tag_name:
                if char.isalnum()==False:
                    tag_name = tag_name.replace(char,'_')
        
        #put underscore in front of uppercase char and set that char to lower
        for char in tag_name:
            if char.isupper() ==True:
                new_char = '_'+char.lower()
                tag_name = tag_name.replace(char,new_char)

        #look for duplicate undescores
        loop_len = len(tag_name)-1
        for i in range (loop_len):
            if i == loop_len:
                break
            if tag_name[i]=='_':
                if tag_name[i] == tag_name[i+1]: 
                    tag_name = tag_name[:i] + tag_name[i + 1:]  
                    loop_len = len(tag_name)-1
        
        #remove leading underscore
        if tag_name[0] == '_':
            tag_name = tag_name[1:]

        #remove trailing underscore
        if tag_name[len(tag_name)-1] == '_':
            tag_name = tag_name[:-1]
        
        #if tag_name length >255, remove underscores from left to right until <=255
        if len(tag_name)>255:
            for i in range(len(tag_name)-1):
                if tag_name[i] == '_':
                    tag_name = tag_name[:i] + tag_name[i+1:]
                    if len(tag_name)<=255:
                        return tag_name

        #prepend resource tag user to match Athena          
        tag_name = 'resource_tags_user_' + tag_name
        
        return tag_name

    def require_user_provided_region(self)-> bool:
        '''
        determine if report needs to have region
        provided by user'''
        return False
    
    def set_run_in_region(self)-> str:
        '''
        if region does not need to be provided
        by user for report, use this predetermined
        region
        '''
        return 'us-east-1'