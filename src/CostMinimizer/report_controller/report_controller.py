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
from pathlib import Path
from datetime import datetime

from .account_discovery_controller import AccountDiscoveryController
from ..utils.term_menu import launch_terminal_menu

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

    def import_provider(self, provider):
        provider = provider.split('_')[0]
        module_path = self.reports_module_path + '.' + provider + '_reports' + '.' + provider
        module = importlib.import_module(module_path, self.writer)

        return getattr(module, provider.title() + 'Reports')
    
    def import_reports(self, force_all_providers_true = False) -> list:
        """
        Import reports from the report providers.
        
        :return: List of imported reports
        """
        # import and return a list of class refernces for all providers

        # provider logic should be placed in reports/<provider_name>_reports/<provider_name>.py
        # providers should have a class named <provider_name>Reports.  For example: "CurReports"
        # provider classes should have two methods setup() and run()

        def import_provider(provider):
            provider = provider.split('_')[0]
            module_path = self.reports_module_path + '.' + provider + '_reports' + '.' + provider
            module = importlib.import_module(module_path, self.writer)

            return getattr(module, provider.title() + 'Reports')

        providers = []
        for provider in self.get_report_providers():
            # only enable specifics reports based on params

            if force_all_providers_true:
                providers.append(import_provider(provider))
            else:
                for argument in self.appConfig.arguments_parsed._get_kwargs():
                    if f'{argument[0]}_reports' == provider and argument[1] == True:
                        providers.append(import_provider(provider))
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

    def report_controller_prerequisites(self):
        self.appConfig.accounts = AccountDiscoveryController()
        self.appConfig.accounts.account_discovery_controller_setup()
        self.appConfig.accounts_metadata = self.appConfig.accounts.accounts_metadata
    
    def _controller_setup(self) -> None:
        """
        Set up the controller by initializing necessary components.
        """
        self.report_controller_prerequisites()
            
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
    
    def run(self):
        """
        Run the report controller, executing the main logic for report generation and processing.
        """
        # run the report controller
        #run any setup instructions for the controller
        # self.report_controller_prerequisites()
        
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

            if not p.enrollment_status:
                self.logger.info('Skipping report provider: %s, not enrolled.', p.name())
                continue

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

