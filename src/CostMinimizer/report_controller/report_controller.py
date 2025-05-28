# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import logging
import json
import traceback
import os
import importlib
import glob
import re
from pathlib import Path
from datetime import datetime
from ..utils.term_menu import launch_terminal_menu
from ..error.error import UnableToDiscoverCustomerLinkedAccounts


# class UnableToDiscoverCustomerLinkedAccounts(Exception):
#     pass

# class UnableToGetTagsFromBubbleWand(Exception):
#     pass

class InvalidCowExecutionType(Exception):
    pass

class InvalidReportDateStamp(Exception):
    pass

class CowReportControllerBase:

    def __init__(self, appConfig, writer) -> None:
        """
        Initialize the CowReportControllerBase class.
        
        :param app: The application instance
        :param writer: The writer object for output
        """
        self.logger = logging.getLogger(__name__)
        self.appConfig = appConfig
        self.report_path = self.appConfig.internals['internals']['reports']['reports_directory']
        self.reports_module_path = self.appConfig.internals['internals']['reports']['reports_module_path']
        self.account_discovery = self.appConfig.internals['internals']['reports']['account_discovery']
        self.user_tag_discovery = self.appConfig.internals['internals']['reports']['user_tag_discovery']
        self.user_tag_values_discovery = self.appConfig.internals['internals']['reports']['user_tag_values_discovery']
        self.reports_absolute_path = Path()
        try:
            # First attempt to find reports folder
            self.reports_absolute_path = Path(os.getcwd()) / self.report_path
            os.listdir(self.reports_absolute_path)
        except (OSError, FileNotFoundError):
            try:
                # Second attempt in src directory
                self.reports_absolute_path = Path(os.getcwd()) / "src" / __name__.split('.')[0] / self.report_path
                os.listdir(self.reports_absolute_path)
            except (OSError, FileNotFoundError) as e:
                self.logger.error(f'Unable to find the reports folder, either under {os.getcwd()} or src/')
                raise RuntimeError("Reports directory not found") from e

        #self.reports_absolute_path = self.appConfig.app_path / self.report_path
        self.report_providers = []
        self.enabled_reports = None
        self.all_providers_completed_reports = []
        self.all_providers_failed_reports = []
        self.reports_in_progress = {}       #dict of providers reports that are in progress
        self.running_report_providers = [] #report providers that have been instantiated and are running
        self.writer = writer

    def get_report_providers(self) -> list:
        """
        Get the list of report providers.
        
        :return: List of report providers
        """
        # return a list of report providers

        # report providers should be placed in a directory named <provider_name>_reports within the reports dir

        report_providers = [
            name for name in os.listdir(self.reports_absolute_path)
            if os.path.isdir(os.path.join(self.reports_absolute_path, name))
            ]
        if '__pycache__' in report_providers:
            report_providers.remove('__pycache__')

        for report_provider in enumerate(report_providers): #log
            self.logger.info('report_provider: %s = %s', str(report_provider[0]), str(report_provider[1]))

        return report_providers

    def import_reports(self, force_all_providers_true = False) -> list:
        """
        Import reports from the report providers.
        
        :return: List of imported reports
        """
        # import and return a list of class refernces for all providers

        # provider logic should be placed in reports/<provider_name>_reports/<provider_name>.py
        # providers should have a class named <provider_name>Reports.  For example: "CurReports"
        # provider classes should have two methods setup() and run()

        providers = []

        for provider in self.get_report_providers():
            # only enable specifics reports based on params

            if (provider == 'ce_reports' and self.appConfig.arguments_parsed.ce) or \
                (provider == 'co_reports' and self.appConfig.arguments_parsed.co) or \
                (provider == 'ta_reports' and self.appConfig.arguments_parsed.ta) or \
                (provider == 'cur_reports' and self.appConfig.arguments_parsed.cur) or \
                force_all_providers_true:
                
                provider = provider.split('_')[0]
                module_path = self.reports_module_path + '.' + provider + '_reports' + '.' + provider
                module = importlib.import_module(module_path, self.writer)

                provider_class = getattr(module, provider.title() + 'Reports')
                providers.append(provider_class)
            else:
                continue

        self.logger.info('Importing: %s report provider(s) found.', len(providers))

        return providers

    def get_completed_reports_from_controller(self) -> list:
        """
        Get the list of completed reports from the controller.
        
        :return: List of completed reports
        """
        #eturn self.all_providers_completed_reports

        #self.get_provider_reports()

        return self.all_providers_completed_reports

    def get_failed_reports_from_controller(self) -> list:
        """
        Get the list of failed reports from the controller.
        
        :return: List of failed reports
        """
        return self.all_providers_failed_reports

class CowReportController(CowReportControllerBase):
    # controller for all enabled reports

    # parameters:
    # app: main app
    # requested_report: list of requested reports
    def __init__(self, appConfig, writer) -> None:
        super().__init__(appConfig=appConfig, writer=writer)
        self.requested_reports = None
        self.report_providers = None

    def _controller_setup(self) -> None:
        """
        Set up the controller by initializing necessary components.
        """
        # Run instructions  necessary to setup the app or controller with
        # further data.  This is including any data that may be internal to
        # AMZN.  Any code internal to AMZN should be marked as #INTERNAL

        #import all enabled reports
        self.report_providers = self.import_reports()

        # add variable required for k2 account validations they
        # will be validated in the k2 report_provider

        #self.appConfig.k2_account_validation_complete = False

        # #INTERNAL: run CUR from bubblewand to collect additional information about the customer linked accounts.
        # This functionality enables use to resolve the customer payer, and obtain account
        # name information from bubblewand.

        for provider in self.report_providers:
            # only 4 types of provider allowed at this stage
            if provider.name() == 'ta' or provider.name() == 'ce' or provider.name() == 'co' or provider.name() == 'cur':
                # The account_discovery report is defined in cow_internals.yaml
                account_discovery_report_name = self.account_discovery.split('.')[0]
                account_discovery_provider = self.account_discovery.split('.')[1]
                account_discovery_class_name = ''.join([ i.title() for i in account_discovery_report_name.split('_')])

                #Injecting customer_account_discovery in case it is not selected
                customer_account_discovery_report = { account_discovery_report_name: account_discovery_provider }
                # JSR TODO Add this to the cow_internals and create a default if it does not exist there.
                # customer_regions_report = { 'customer_regions' : 'cur' }

                # normally we would use self.appConfig.reports.get_all_enabled_reports() for discovery,
                # however, since we are injecting the account discovery query above there is not need.  We
                # use customer_account_discovery_report
                a_provider = provider(self.appConfig, customer_account_discovery_report, account_discovery=True, dependency_run=False, dependent_report=None)
                a_provider.auth()
                a_provider.setup()
                reports = a_provider.import_reports(provided_report_metadata={account_discovery_report_name: account_discovery_class_name,
                    'customer_regions': 'CustomerRegions'})

                #generate cache if customer changes spend config (needs to be passed in as dict of list)
                customer_min_spend_from_config=[str(self.appConfig.customers.get_customer_data(self.appConfig.customers.selected_customer)['min_spend'])]

                #expiration settings from database
                account_cache_settings_from_database=self.appConfig.cow_config.get_cache_settings()['account_discovery']

                try:
                    reports_in_progress = a_provider.run(reports, customer_min_spend_from_config, account_cache_settings_from_database)
                except Exception as exc:
                    raise UnableToDiscoverCustomerLinkedAccounts(f'Unable to discover customer accounts and regions for {self.appConfig.customers.selected_customer}.  Is Bubblewand enabled?') from exc

                a_provider.fetch_data(reports_in_progress,
                    customer_min_spend_from_config,
                    account_cache_settings_from_database,
                    type=None, display=True, cow_execution_type=None)

                completed_reports, _ = a_provider.get_completed_reports_from_provider()

                if len(completed_reports) == 2:
                    accounts = completed_reports[0].get_report()
                    regions = completed_reports[1].get_report()
                else:
                    raise UnableToDiscoverCustomerLinkedAccounts(f'Unable to discover customer accounts and regions for {self.appConfig.customers.selected_customer}.')

                return (accounts['data'], regions['data'])
            
    def _get_user_tags(self) -> None:
        """
        Get user tags for the report.
        """
         #import all enabled reports
        self.report_providers = self.import_reports()
        
        '''
        #INTERNAL: run CUR from bubblewand to collect schema colummns for user defined-tags.
        Switching this to K2 and doing some reverse-engineering of the Athena key renaming.

        '''
    
    def _get_user_tag_values(self, user_tag_list) -> None:
        """
        Get user tag values for the given tag list.
        
        :param user_tag_list: List of user tags
        """
         #import all enabled reports
        self.report_providers = self.import_reports()
        
        '''
        #INTERNAL: run CUR from bubblewand to collect schema colummns for user defined-tags.

        '''
                
    def fetch(self, cow_execution_type=None, dependency_type=None):
        """
        Fetch reports based on the execution type and dependency type.
        
        :param cow_execution_type: Type of execution (sync/async)
        :param dependency_type: Type of dependency
        """
        # fetch data for all enabled reports

        # cow_execution_type: sync
        # dependency_type: parent or dependent

        # because we have to repeat this message and process many times, we will create a function to do it for us
        def status_message(app, dependency_type, report_name, report_object, provider_object, msg_type='FAILED'):
            report_object.status = msg_type
            if msg_type == 'FAILED':
                app.console.print(f'[green]Found [yellow]{dependency_type} [green]report [yellow]{report_name} [green]Status: [red]{msg_type} [green]Provider: [yellow]{provider_object.name()}[green]. [yellow]Skipping.')
                self.logger.info('Fail information for: %s.  Traceback: %s', report_name, traceback.format_exc())
                app.alerts['async_fail'].append({report_name:'FAILED'})
                if report_object not in provider.failed_reports:
                    provider_object.failed_reports.append(report_object)
            else:
                app.console.print(f'[green]Found {dependency_type} [green]report [yellow]{report_name} [green]Status: [yellow]{msg_type} [green]Provider: [yellow]{provider_object.name()}')
                app.alerts['async_success'].append({report_name:msg_type})
                if report_object not in provider.completed_reports:
                    provider_object.completed_reports.append(report_object)

        self.appConfig.console.print(f'[yellow]FETCHING DATA for {len(self.running_report_providers)} type of reports -------------------------------------------------------------------------')

        for provider in self.running_report_providers:

            if provider.name() not in self.enabled_reports.values():
                self.logger.info('Skipping report provider: %s, no reports selected from provider.', provider.name())
                continue

            try:
                #sync execution
                if self.appConfig.cow_execution_type == 'sync':
                    s = datetime.now()

                    provider.fetch_data(provider.reports_in_progress, type='base')

                else:
                    raise InvalidCowExecutionType(f'Invalid CostMinimizer execution type: {self.appConfig.cow_execution_type}')

            except InvalidCowExecutionType as e:
                self.logger.error(f"Invalid execution type: {str(e)}")
                continue

            e = datetime.now()
            self.logger.info('Running fetch() for provider %s: finished in %s', provider.name(), e - s)

    def calculate_savings(self):
        """
        Calculate savings for the reports.
        """

        for provider in self.running_report_providers:

            if provider.name() not in self.enabled_reports.values():
                self.logger.info('Skipping report provider: %s, no reports selected from provider.', provider.name())
                continue

            s = datetime.now()
            self.logger.info(f'Running: calculate savings for provider {provider.name()}')
            provider.calculate_savings()
            e = datetime.now()
            self.logger.info('Calculating savings for provider %s: finished in %s', provider.name(), e - s)

    def get_provider_reports(self):
        """
        Get reports from all providers.
        """

        self.all_providers_completed_reports = []
        self.all_providers_failed_reports = []
        for provider in self.running_report_providers:

            if provider.name() not in self.enabled_reports.values():
                self.logger.info('Skipping report provider: %s, no reports selected from provider.', provider.name())
                continue

            completed_reports, failed_reports = provider.get_completed_reports_from_provider()

            self.all_providers_completed_reports.extend(completed_reports)
            self.all_providers_failed_reports.extend(failed_reports)

    # def display_menu_for_reports(self, title:str, customer_report_folders:list, multi_select=True, show_multi_select_hint=True, show_search_hint=True):
    #     # display menu for reports
    #     subtitle = title
    #     menu_options_list = launch_terminal_menu(
    #         customer_report_folders,
    #         title=title,
    #         subtitle=subtitle,
    #         multi_select=multi_select,
    #         show_multi_select_hint=show_multi_select_hint,
    #         show_search_hint=show_search_hint)

    #     return menu_options_list

    # JSR this is already defined below
    # def get_menu_selection_for_async_reports(self) -> list:
    #     # display menu for reports and return the menu selection

    #     #get all distinct reports from database
    #     # JSR TODO: Make this a function in the database class
    #     sql = 'SELECT DISTINCT(start_time), comment  FROM "main"."cow_cowreporthistory"'
    #     result = self.appConfig.database.select_records(sql, rows='all')

    #     #join for menu display
    #     menu_options = [' | '.join(row) for row in result]

    #     #display menu for reports
    #     menu_selection = self.display_menu_for_reports(title='Select report to check status', customer_report_folders=menu_options, multi_select=False, show_multi_select_hint=False, show_search_hint=False)
    #     #obtain the date stamp from the menu selection
    #     menu_selection = menu_selection[0].split('|')[0].strip()

    #     return menu_selection

    def display_menu_for_reports(self, title:str, customer_report_folders:list, multi_select=True, show_multi_select_hint=True, show_search_hint=True):
        '''display menu for reports'''
        subtitle = title
        menu_options = ['ALL'] + customer_report_folders
        menu_options_list = launch_terminal_menu(
            menu_options,
            title=title,
            subtitle=subtitle,
            multi_select=multi_select,
            show_multi_select_hint=show_multi_select_hint,
            show_search_hint=show_search_hint)
        
        if isinstance(menu_options_list, tuple) and menu_options_list[0] == 'ALL':
            return [(option, i) for i, option in enumerate(customer_report_folders)]
        elif isinstance(menu_options_list, list) and 'ALL' in [option for option, _ in menu_options_list]:
            return [(option, i) for i, option in enumerate(customer_report_folders)]
        else:
            return menu_options_list
    
    # def get_menu_selection_for_async_reports(self) -> list:
    #     '''display menu for reports and return the menu selection'''

    #     #get all distinct reports from database
    #      # JSR TODO: Make this a function in the database class
    #     sql = 'SELECT DISTINCT(start_time), comment FROM "main"."cow_cowreporthistory"'
    #     try:
    #         result = self.appConfig.database.select_records(sql, rows='all')
    #     except Exception as e:
    #         self.logger.error(f"Database query failed: {e}")
    #         return []

    #     #glob for the folder and combine customer name into the folder
    #     menu_options = []
    #     for row in result:
    #         if len(row) > 0:
    #             folder_date_glob_pattern = f'*{row[0]}*'
    #             try:
    #                 found_folder_with_customer_name = glob.glob(str(self.appConfig.report_directory) + '/' + folder_date_glob_pattern) #list
    #             except Exception as e:
    #                 self.logger.error(f"File system operation failed: {e}")
    #                 continue
    #         if len(row) == 2 and found_folder_with_customer_name:
    #             try:
    #                 if Path(found_folder_with_customer_name[0]).is_dir():
    #                     # Don't use 'stem', use 'name'. https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.name
    #                     folder = Path(found_folder_with_customer_name[0]).name
    #                     folder_tag = row[1]
    #                     menu_options.append(folder + ' | ' + folder_tag)
    #             except Exception as e:
    #                 self.logger.error(f"File system operation failed: {e}")
    #                 continue

    #     #display menu for reports
    #     menu_selection = self.display_menu_for_reports(title='Select report to check status', customer_report_folders=menu_options, multi_select=False, show_multi_select_hint=False, show_search_hint=False)

    #     #obtain the date stamp from the menu selection
    #     menu_selection = menu_selection[0].split('|')[0].strip()

    #     #match app start time to that of the selection from the menu
    #     pattern = r'\d{4}-(?:0?[1-9]|1[0-2])-(?:0?[1-9]|[12][0-9]|3[01])-(?:0?[0-9]|1[0-9]|2[0-3])-\d{2}'
    #     match = re.search(pattern, menu_selection)

    #     if isinstance(match, re.Match):
    #         menu_selection = match[0]

    #     return menu_selection


    def run(self):
        """
        Run the report controller, executing the main logic for report generation and processing.
        """
        # run the report controller
        #run any setup instructions for the controller
        if self.appConfig.mode == 'cli':
            with self.appConfig.console.status("Report Controller: Importing report providers..."):
                self.report_providers = self.import_reports()
        elif self.appConfig.mode == 'module':
            self.report_providers = self.import_reports()

        self.enabled_reports = self.appConfig.reports.get_all_enabled_reports()

        enabled_report_request = { 'enabled_reports': self.enabled_reports }
        self.appConfig.console.status(json.dumps(enabled_report_request))

        for provider in self.report_providers:
            self.appConfig.console.print(f"\n[yellow]{provider.long_name(self).ljust(120, '-')}")
            self.logger.info('Running report provider: %s', provider.name())

            if provider.name() not in self.enabled_reports.values():
                self.logger.info('Skipping report provider: %s, no reports selected from provider.', provider.long_name(self))
                continue

            #create each provider
            p = provider(self.appConfig)

            self.running_report_providers.append(p)

            #run each providers authentication logic
            s = datetime.now()
            p.auth()
            e = datetime.now()
            self.logger.info('Running auth() for provider %s: finished in %s', p.name(), e - s)

            #run each providers setup logic
            s = datetime.now()
            p.setup(run_validation=True)
            e = datetime.now()
            self.logger.info('Running setup() for provider %s: finished in %s', p.name(), e - s)

            #run mandatory reports required for pptx generation. (PowerPoint reports)
            self.appConfig.console.print(f'\n[green]Running [yellow]PowerPoint reports [green]for [yellow]{p.name()} [green]provider...')
            p.mandatory_reports(type='base')
            
            #run each providers query logic

            if self.appConfig.mode == 'cli':
                self.appConfig.console.print(f'[green]Running reports syncronously for [yellow]{p.name()} [green]provider...\n')

            s = datetime.now()
            # execute run() function defined in 
            self.reports_in_progress[p.name()] = p.run(type='base', cow_execution_type=self.appConfig.cow_execution_type)


            e = datetime.now()
            self.logger.info('Running run() for provider %s: finished in %s', p.name(), e - s)

