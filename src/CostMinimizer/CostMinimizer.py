# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

#imports
import sys
import os
import sysconfig
import logging
import boto3
import warnings
#specific imports
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path
#application imports
from .conf.configuration_manager import ConfigurationManager
from .arguments.arguments import ToolingArguments
from .commands.factory import CommandFactory
from .security.cow_authentication import Authentication
from .patterns.singleton import Singleton
from .report_request_parser.report_request_parser import ToolingReportRequest

# Suppress future warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

@dataclass
class AppliConf:
    """Configuration data class for the application"""
    mode: str = 'cli'
    report_input_file: Optional[str] = None
    selected_customer: Optional[str] = None
    cow_execution_type: str = 'sync'
    tag: Optional[str] = None
    send_mail: Optional[bool] = None
    input_files: Optional[List[str]] = None
    question: Optional[str] = None
    debug: bool = False
    datasource: str = 'yaml'
    report_file_name: str = 'CostMinimizer.xlsx'
    cow_internals = {}

@dataclass
class AlertState(Singleton):
    """Data class for managing application alerts"""
    alerts: Dict[str, Any] = field(default_factory=lambda: {
        'aws_cow_profile': None,
        'midway': None,
        'customer_not_found': None,
        'report_failure': None,
        'missing_secret': None,
        'incorrect_secret': None,
        'secret_not_validated': None,
        'secret_confirmation_error': None,
        'secret_updated_successfully': None,
        'cache_file_error': None,
        'comparison': None,
        'async_status': None,
        'async_success': [],
        'async_unfinished': None,
        'async_fail': [],
        'async_error': [],
        'async_message': [],
        'calculate_fail': [],
        'calculate_success': []
    })

class AuthenticationManager:
    """Manages AWS authentication and session handling"""
    def __init__(self, app_instance):
        self.appInstance = app_instance
        self.cow_authentication = None
        self.aws_cow_account_boto_session = None
        from .config.config import Config
        self.config = Config()


    def setup_authentication(self) -> None:
        if not self.config.arguments_parsed.version:
            self.cow_authentication = Authentication()
            self.aws_cow_account_boto_session = self.configure_boto_session()

            if not self.aws_cow_account_boto_session: 
                self.cow_authentication.recreate_all_profiles()

            if self.appInstance.AppliConf.mode == 'cli':
                self.handle_cli_authentication()

    def configure_boto_session(self) -> Optional[boto3.Session]:
        try:
            session = self.cow_authentication.create_account_session()
            if session:
                self.cow_authentication.log_session_access_key(session)
            return session
        except boto3.exceptions.Boto3Error as e:
            self.appInstance.logger.error(f"Failed to configure boto session: {str(e)}")
            return None

    def handle_cli_authentication(self) -> None:
        login_type = 'aws_profile' #Todo this should come from configuration

        self.cow_authentication.update_login_history(login_type)

class App:
    """Main application class for AWS Cost Optimization Workshop tool"""
    def __init__(self, p_config: AppliConf):
        self.AppliConf = p_config
        self.start = datetime.now()
        self.report_time = self.start.strftime("%Y-%m-%d-%H-%M")
        self.platform = sysconfig.get_platform()
        self.app_path = Path(os.path.dirname(__file__))

        self.alert_state = AlertState()
        self.logger = logging.getLogger(__name__)
        self.arguments_parsed = None

        self._initialize_managers()
        self._setup_application()

        self.config_manager.appConfig.default_report_request = self.config_manager.appConfig.report_output_directory  / self.config_manager.appConfig.internals['internals']['reports']['default_report_request']

    def _initialize_managers(self) -> None:
        self.config_manager = ConfigurationManager()
        self.auth_manager = AuthenticationManager(self)

    def _setup_application(self) -> None:
        self._parse_arguments()
        self._setup_authentication()
        self._initialize_database()

    def _parse_arguments(self) -> None:
        """
        Parse provided command line or arguments into the imported class.
        Determine if report input file is provided on command line or
        via argument into this class.  Substitute accordingly and pass
        into CowArguments() which will parse against argparse.
        """
        raw_arguments = sys.argv[1:]
        self.tooling_arguments = ToolingArguments(raw_arguments)
        self.config_manager.appConfig.arguments_parsed = self.tooling_arguments.command_line_arguments()
        self.async_type = self.tooling_arguments.set_data_request_type()

    def _setup_authentication(self) -> None:
        self.auth_manager.setup_authentication()
        self.config_manager.appConfig.auth_manager = self.auth_manager

    def _initialize_database(self) -> None:
        self.config_manager.appConfig.database_initial_defaults( self)
        self.installation_type = self.config_manager.appConfig.installation_type

        # Assign cur_db value from arguments if any
        if hasattr(self.config_manager.appConfig.arguments_parsed, 'cur_db'):
            self.config_manager.appConfig.cur_db_arguments_parsed = self.config_manager.appConfig.arguments_parsed.cur_db

        # Assign cur_table value from arguments if any
        if hasattr(self.config_manager.appConfig.arguments_parsed, 'cur_table'):
            self.config_manager.appConfig.cur_table_arguments_parsed = self.config_manager.appConfig.arguments_parsed.cur_table

    def get_arguments_parsed(self):
        '''Return argparse parsed command line arguments'''
        return self.config_manager.appConfig.arguments_parsed

    def get_arguments_parser(self):
        """
        Return the argument parser object.

        :return: The argument parser
        """
        return self.tooling_arguments.parser

    def report_request_parse(self, parsed_reports_from_menu=None) -> tuple:
        """
        Parse the report request.

        :param parsed_reports_from_menu: Reports parsed from the menu
        :return: Tuple containing parsed report information
        """
        ''' parse and return report request'''

        if self.AppliConf.mode == 'cli':
            '''
            In cli mode - we first check if there is a report request yaml file provided with the -f option.
            Next we check if there is a report request file in the default location.
            Else we check for the report request specified on the command line.
            '''
            try:
                if self.config_manager.appConfig.default_report_request.is_file():
                    #Try file from the cow_internals default location
                    report_request = ToolingReportRequest(self, self.config_manager.appConfig.default_report_request, '')
                    datasource_file = self.config_manager.appConfig.default_report_request
                else:
                    #Try with data from report and customer input menus
                    self.datasource = 'database'
                    datasource_file = self.config_manager.appConfig.database.database_file.resolve()
                    report_request = ToolingReportRequest(
                        self,
                        self.config_manager.appConfig.default_report_request,
                        '',
                        read_from_database=True,
                        reports_from_menu=parsed_reports_from_menu
                        )

                if self.AppliConf.debug:
                    self.console.print(f'[blue underline]Report data source from {self.datasource} : {datasource_file}')

                self.logger.info(f'Running in {self.AppliConf.mode} mode: Report data source from {self.datasource} : {datasource_file}')
                return report_request.get_all_reports()
            except IOError as e:
                self.logger.error(f"Error accessing file: {str(e)}")
                raise
            except Exception as e:
                self.logger.error(f"Error creating ToolingReportRequest: {str(e)}")
                raise
        elif self.AppliConf.mode == 'module':
            #Try with data from report and customer input menus
            self.datasource = 'database'
            datasource_file = self.config_manager.appConfig.database.database_file.resolve()
            report_request = ToolingReportRequest(
                self,
                self.config_manager.appConfig.default_report_request,
                self.arguments_parsed.customer,
                read_from_database=True,
                reports_from_menu=parsed_reports_from_menu
                )

            self.logger.info(f'Running in {self.mode} mode: Report data source from {self.datasource} : {datasource_file}')
            return report_request.get_all_reports()

    @property
    def is_cli_mode(self) -> bool:
        """Check if running in CLI mode."""
        return self.AppliConf.mode == 'cli'

    def clear_cli_terminal(self):
        """
        Clear the CLI terminal screen.
        """
        #clear the console screen in cli mode
        if self.is_cli_mode:
            # For Windows
            if os.name == 'nt':
                os.system('cls')
            # For Unix/Linux/MacOS
            else:
                os.system('clear')

    def validate_database_configuration(self) -> bool:
        """
        Validate the database configuration.

        :return: True if the configuration is valid, False otherwise
        """
        '''validate configuration table has entry in the database'''
        if 'configure' not in self.config_manager.appConfig.arguments_parsed:
            if len(self.config_manager.appConfig.internals) == 0:
                return False

        return True

    def main(self) -> Any:
        """Main execution method"""
        try:
            if self.AppliConf.mode == 'cli':
                self.clear_cli_terminal()

            self.logger.info(f'Starting CostMinimizer tool in {self.AppliConf.mode} mode')

            args = self.get_arguments_parsed()

            if not self.validate_database_configuration():
                self._handle_missing_configuration()
                return

            cmd = CommandFactory().create(arguments=args, app=self)

            if args.question:
                return self._handle_question_mode(args, cmd)
            else:
                return self._handle_standard_mode(cmd)
        except Exception as e:
            self.logger.error(f"An error occurred: {str(e)}")
            print(f"An unexpected error occurred. Please check the logs for more information.")
            return None

    def _handle_missing_configuration(self) -> None:
        message = 'CostMinimizer configuration does not exist. Run CostMinimizer --configure and select option 1.'

        self.logger.info(message)
        print(message)
        sys.exit(0)

    def _handle_question_mode(self, args: Any, cmd: Any) -> Any:
        if args.input_files:
            self._process_input_files(args)
        return cmd.execute()

    def _handle_standard_mode(self, cmd: Any) -> Any:
        result = cmd.run()
        return result if self.AppliConf.mode == 'module' else None

    def _process_input_files(self, args: Any) -> None:
        self.input_files = args.input_files
        self.question = args.question or input("Please enter your question for Q: ")
        print(f"Processing files: {self.input_files}")
        print(f"Question for AWS Bedrock: '{self.question}'")

def main():
    """
    Main entry point for the application.
    """
    config = AppliConf(mode='cli', report_input_file='~/cow')
    app = App(config)
    return app.main()

if __name__ == "__main__":
    main()
