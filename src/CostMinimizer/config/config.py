# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

__TOOL_CONF_INTERNALS__ = "cm_internals.yaml"

from ..constants import __tooling_name__
from ..commands.configure_tooling import ConfigureToolingCommand

"""
Configuration module for the Cost Optimization Tooling.
This module handles loading, managing, and applying various configuration settings for the COW application.
It interacts with YAML files, databases, and environment variables to set up the application's configuration.
"""

import yaml
import os, sys
import logging
import sysconfig
import pandas as pd
from pathlib import Path
from ..patterns.singleton import Singleton
from rich.console import Console
from datetime import datetime
from typing import Optional, Dict, List, Any


from ..utils.yaml_loader import import_yaml_file, YamlFileSyntaxError
from ..security.cow_authentication import Authentication
from ..commands.available_reports import AvailableReportsCommand
from ..version.version import ToolingVersion
from ..security.cow_authentication import AuthenticationManager
from .database import ToolingDatabase

class UnableToLoadCowConfigurationFileException(Exception):
    pass

class UnableToDetermineRootDir(Exception):
    pass

class ErrorInConfigureCowInsertDB(Exception):
    pass

class Config(Singleton):

    '''
    note: 

    Class is responsible for holding all configuration parameters, 
    methods to setup the tool and methods to setup the database
    '''

    def __init__(cls):
        cls.logger = logging.getLogger(__name__)
        cls.cow_execution_type = 'sync'
        cls.tag: Optional[str] = None
        cls.debug: bool = False
        
    def setup(cls, mode='cli'):
        '''setup the cow database and user configuration'''
        cls.console = Console()
        cls.mode = mode
        
        cls.app_path = cls._setup_app_path()
        cls.conf_dir = cls.app_path / 'conf'
        cls.installation_type = cls.__set_installation_type()
        cls.platform = cls._setup_platform()
        cls.default_selected_region = 'us-east-1' #TODO this should come from parameters
        cls.default_selected_regions = 'us-east-1' #TODO this should come from parameters
        cls.internals_file = cls.app_path / 'conf' / __TOOL_CONF_INTERNALS__
        cls.internals, cls.origin_internals_values = cls.__load_cow_config(config_file=cls.internals_file)
        cls.report_directory, cls.report_output_directory = cls.__set_report_directory(cls.installation_type)
        cls.default_report_request = cls.report_output_directory  / cls.internals['internals']['reports']['default_report_request']
        
        cls._setup_logging()
        cls._setup_report_time()
        cls._setup_database(cls) #setup database class
        cls.write_installation_type() #write installation type into database configuration table
        cls._setup_user_configuration() #populate cls.config dictionary with account values
        cls._setup_internals_parameters() #load tool parameters

    def database_initial_defaults(cls, arguments_parsed=None):
        '''
        TODO rename this function as it does not have anything to do with 
        database initial defaults, rather automated configuration and 
        the writing of reports to database
        '''

        #if tool not configured; attempt automatic configuration
        #TODO in the future this functionality shouold be moved to ConfigureToolingCommand()
        cls.attempt_automatic_configuration()

        #write all available reports to database
        cls.write_available_reports_to_database(cls.usertag_support(arguments_parsed))

    def tool_configuration_status(cls) -> bool:
         '''determine if configuration exists in database'''
         #TODO come up with better mechinism than output_folder 
         if (cls.config.get('output_folder') is None):
            return False
         return True
    
    def prompt_for_automated_configuration(cls) -> None:
        '''prompt user for automated configuration'''
        # Check if --auto-update-conf parameter is set
        if hasattr(cls, 'arguments_parsed') and hasattr(cls.arguments_parsed, 'auto_update_conf') and cls.arguments_parsed.auto_update_conf:
            return True
            
        cls.console.print(f'[blue]Tool configuration is not finished.  This appears to be a new installation. [/blue]')
        cls.console.print(f'[blue]Would you like me to attempt an automatic configuartion based on your authentication variables?[/blue]')
        answer = input('Enter [y/n]: ')

        if answer == 'y':
            return True
        
        return False

    def attempt_automatic_configuration(cls) -> None:
        def exit_automatic_configuration(error=True):
            error_message=f'[blue]Please run [bold]"CostMinimizer --configure"[/bold] to configure your account.[/blue]'
            if error:
                cls.console.print(f'[red]Automatic configuration failed. Please run [bold]"CostMinimizer --configure"[/bold] to configure your account.[/red]')
            cls.console.print(error_message)
            sys.exit(0)
        
        if not cls.tool_configuration_status():
            if cls.prompt_for_automated_configuration():
                try:
                    cls.automate_launch_cow_cust_configure()

                    cls.console.print(f'[green]Automatic configuration successfully performed ![/green]')
                    cls.console.print(f'[yellow]WELCOME ! This is the first time CostMinimizer is launched, please configure the tooling !')
                    cls.console.print(f'[yellow]        Select the option 1)    Manual CostMinimizer Tool Configuration (setup my AWS account) !!![/yellow]')
                    cls.console.print(f'[yellow]        In case you want to use CUR, verify or update the values of cur_db & cur_table"[/yellow]')
                    ConfigureToolingCommand().run()

                except Exception as e:
                    exit_automatic_configuration()
            else:
                exit_automatic_configuration(error=False)
    
    def usertag_support(cls, arguments_parsed=None) -> bool:
        '''determine if user tags are enabled'''
        if hasattr(arguments_parsed, 'usertags'):
            u_tags = arguments_parsed.usertags
        else:
            u_tags = False
        
        return u_tags
    
    def _setup_logging(cls) -> None:
        log_config = cls.internals['internals']['logging']
        log_file_path = cls.report_directory / log_config['log_file']

        # check if cls.report_directory exists as a directory, otherwize create the folder
        if not cls.report_directory.is_dir():
            cls.report_directory.mkdir(parents=True, exist_ok=True)

        cls._cleanup_log_file(log_file_path)
        logging.basicConfig(
            filename=log_file_path.resolve(),
            format=log_config['log_format'],
            level=log_config['log_level_default'],
            force=True
        )

    def  _cleanup_log_file(cls, log_file_path: Path) -> None:
        if log_file_path.is_file():
            try:
                os.remove(log_file_path.resolve()) #
            except FileNotFoundError as r:
                cls.logger.info(f"Failed to remove log file: {r}")
            except:
                raise
    
    def _setup_report_time(cls) -> None:
        cls.start = datetime.now()
        cls.report_time = cls.start.strftime("%Y-%m-%d-%H-%M")
        cls.end = None

    def _setup_home_directory(cls) -> Path:
        '''setup the home directory for the application'''
        cls.local_home = Path.home()
        
        if os.getenv('APP_CM_USER_HOME_DIR'):
            return Path(os.getenv('APP_CM_USER_HOME_DIR'))
        else:
            return cls.local_home
    
    def _setup_platform(cls) -> str:
        return sysconfig.get_platform()

    def _setup_app_path(cls) -> Path:
        #Path() of application business logic
        return Path(os.path.dirname(__file__)).parent 

    def __setup_default_internals_paramaters(cls) -> str:
        '''setup the default internals parameters'''

        internals_yaml_defaults = """
internals:
  db_fields_to_update:
    - version
    - genAI.default_provider
  boto:
    default_profile_name: CostMinimizer
    default_profile_role: Admin
    default_region: us-east-1
    default_secret_name: CostMinimizer_secret
  comparison:
    column_group_by: CostType
    column_report_name: CostDomain
    column_savings: estimated_savings
    filename: comparison.xlsx
    include_details_in_xls: 'No'
    name_xls_main_sheet: 0-Cost_Pillar
    reports_directory: reports
  cur_customer_discovery:
    aws_profile: '{dummy_value}_profile'
    db_name: customer_cur_data
    region: us-east-1
    role: AthenaAccess
    aws_cow_s3_bucket: s3://aws-athena-query-results-{dummy_value}-us-east-1/
    secrets_aws_profile: '{dummy_value}_profile'
    table: customer_all
  cur_reports:
    cur_directory: cur_reports
    lookback_period: 1
    report_directory: reports
  ce_reports:
    ce_directory: ce_reports
    lookback_period: 1
    report_directory: reports
  co_reports:
    co_directory: co_reports
    lookback_period: 1
    report_directory: reports
  ta_reports:
    ta_directory: ta_reports
    lookback_period: 1
    report_directory: reports
  ec2_reports:
    ec2_directory: ec2_reports
    lookback_period: 1
    report_directory: reports
  database:
    database_directory_for_container: .cow
    database_directory_for_local: cow
    database_file: CostMinimizer.db
  logging:
    log_directory: cow
    log_file: CostMinimizer.log
    log_format: '%(asctime)s - %(process)d  - %(name)s - %(levelname)s - %(message)s'
    log_level_default: INFO
    logger_config: logger.yaml
  reports:
    account_discovery: customer_account_discovery.cur
    async_report_complete_filename: async_report_complete.txt
    async_run_filename: async_run.txt
    cache_directory: cache_data
    default_decrypted_report_request: report_request_decrypted.yaml
    default_encrypted_report_request: report_request_encrypted.yaml
    default_report_request: report_request.yaml
    expire_file_cache: 1
    report_output_directory: cow
    report_output_directory_for_container: .cow
    report_output_name: CostMinimizer.xlsx
    reports_directory: report_providers
    reports_module_path: CostMinimizer.report_providers
    selection_file: .selection.json
    tmp_folder: .tmp
    web_client_report_refresh_seconds: 120
    user_tag_discovery: user_tag_discovery.k2
    user_tag_values_discovery: user_tag_values_discovery.cur
  results_folder:
    enable_bucket_for_results: False
    bucket_for_results: aws-athena-query-results-{dummy_value}-us-east-1
  genAI:
    default_provider: bedrock
    default_provider_region: us-east-1
    default_genai_model: anthropic.claude-3-5-sonnet-20240620-v1:0
    inference_profile_arn: 
  version: 0.0.1
"""
        return internals_yaml_defaults
    
    def _setup_database(cls, config):
        """Create database and all tables if needed"""
        cls.database = ToolingDatabase()

        # in case the API interfaces are not accessible to get the ec2 instances prices 
        cls.database.insert_awspricingec2()

        # in case the API interfaces are not accessible to get the db instances prices 
        cls.database.insert_awspricingdb()

        # in case the API interfaces are not accessible to get the lambda instances prices 
        cls.database.insert_awspricinglambda()

        # in case the API interfaces are not accessible to get the gravition instances equivalence 
        cls.database.insert_gravitonconversion()

        #process table schema updates
        cls.database.process_table_schema_updates()

    def __set_installation_type(cls) -> str:
        '''
        set installation type:

        return values:
        - container_install
        - local_install
        '''

        container_deployment_file = cls.app_path / 'conf' / "container.txt"

        if Path.is_file(container_deployment_file):
            cls.installation_type = 'container_install'
        else:
            cls.installation_type = 'local_install'

        return cls.installation_type
      
    def __set_report_directory(cls, installation_type: str) -> Path:
        '''
        set report directory:

        return values:
        - cow
        - .cow
        '''
        home_directory = cls._setup_home_directory()

        if installation_type == 'container_install':
          #on container the mapping is to /root/.cow inside the container, on local_install it is $HOME/cow
          report_directory = home_directory / cls.internals['internals']['reports']['report_output_directory_for_container']
          report_output_directory = home_directory / cls.internals['internals']['reports']['report_output_directory']
        else:
          #local_install
          report_directory = cls.local_home / cls.internals['internals']['reports']['report_output_directory']
          report_output_directory = report_directory

        return report_directory, report_output_directory
    
    def __load_cow_config(cls, config_file=None):
        """
        Load COW configuration from a YAML file or use default values.
        """
        try:
            yaml_config = import_yaml_file(config_file, "r")
            origin_internals_values = 'yaml'
        except YamlFileSyntaxError as e:
            #Syntax errors in yaml are an app breaking error
            print(f'[Error]: Yaml file syntax: {e}')
            cls.logger.info(f'[Error] Yaml file syntax: {e}')
            raise
        except Exception as e:
            #File not found is not a breaking error.  Load config from internals.
            cls.logger.info(f"Unable to find internals file: {config_file} (searching for values in the database)")
            
            # if internal yaml file does not exists, then load the default factory values from __setup_default_internals_paramaters()
            yaml_config = yaml.safe_load(cls.__setup_default_internals_paramaters())
            origin_internals_values = 'config'

        return yaml_config, origin_internals_values
    
    def get_app_path(cls) -> Path:
        """
        Determine and return the root directory of the application.
        """
        '''return root directory of app abs path if we find the CostMinimizer.py file'''
        
        entry_point = cls.app_path / "CostMinimizer.py"
        
        if entry_point.is_file():
            return cls.app_path 

        raise UnableToDetermineRootDir("Unable to determine application path directory using get_app_path function.")
    
    def _setup_user_configuration(cls) -> None:
        '''setup user configuration from database'''

        #fetch CostMinimizer configuration from database
        db_config = cls.database.get_cow_configuration()

        cls.config = {}
        if len(db_config) > 0:
            cls.config['aws_cow_account'] = db_config[0][1]
            cls.config['aws_cow_profile'] = db_config[0][2]
            cls.config['sm_secret_name'] = db_config[0][3]
            cls.config['output_folder'] = db_config[0][4]
            cls.config['installation_mode'] = db_config[0][5]
            cls.config['container_mode_home'] = db_config[0][6]
            cls.config['cur_db'] = db_config[0][7]
            cls.config['cur_table'] = db_config[0][8]
            cls.config['cur_region'] = db_config[0][9]
            cls.config['aws_cow_s3_bucket'] = db_config[0][10]
            cls.config['ses_send'] = db_config[0][11]
            cls.config['ses_from'] = db_config[0][12]
            cls.config['ses_region'] = db_config[0][13]
            cls.config['ses_smtp'] = db_config[0][14]
            cls.config['ses_login'] = db_config[0][15]
            cls.config['ses_password'] = db_config[0][16]
            cls.config['costexplorer_tags'] = db_config[0][17]
            cls.config['costexplorer_tags_value_filter'] = db_config[0][18]
            cls.config['graviton_tags'] = db_config[0][19]
            cls.config['graviton_tags_value_filter'] = db_config[0][20]
            cls.config['current_month'] = db_config[0][21]
            cls.config['day_month'] = db_config[0][22]
            cls.config['last_month_only'] = db_config[0][23]
            cls.config['aws_access_key_id'] = db_config[0][24]
            cls.config['aws_secret_access_key'] = db_config[0][25]
            cls.config['cur_s3_bucket'] = db_config[0][26]
    
    def _setup_internals_parameters(cls) -> None:
        '''setup internals parameters from database'''

        # Priority of the origin of internals parameters : 
        #   1) DB if exists 
        #   2) yaml file if exists 
        #   3) Config class defaults values

        #fetch CostMinimizer internals parameters from database if exist
        db_internals_params = cls.database.fetch_internals_parameters_table()

        # if internals parameters exist in the database
        if db_internals_params:
            #cls.internals = db_internals_params

            # if internals yaml file exist also
            if (cls.origin_internals_values == 'yaml'):
               
                # force the update of specific fields in the databases like version number
                try:
                    list_of_fields_to_update_in_db = cls.internals['internals']['db_fields_to_update']
                    if (len(list_of_fields_to_update_in_db) == 0):
                        list_of_fields_to_update_in_db = ['internals.version']
                except:
                    list_of_fields_to_update_in_db = []

                cls.database.update_internals_parameters_table_from_yaml_file(cls.internals, '', list_of_fields_to_update_in_db)
                cls.logger.info(f'Successfully loaded internals parameters from the database & internals yaml file found => Fieds modified: {list_of_fields_to_update_in_db}')
            else:
                cls.logger.info(f'Successfully loaded internals parameters from the database, but internals yaml file not found (no db fields modified)')
                
                ToolingVersion.update_version(cls, cls.internals['internals']['version'])

        # if no paramters are already stored in the database
        else:
            # Db does not contains internals values, so write them
            # cow_internals contains either yaml file values or default factory from CowConfig class if yaml does not exists
            cls.database.write_internals_parameters_table(cls.internals)
            cls.console.print(f'[green]\nSuccessfully write internals parameters from yaml file (or default if not exists) to database ![/green]')

    def setup_authentication(cls) -> None:
        '''
        setup authentication
        '''

        #setup authentication
        cls.auth_manager = AuthenticationManager()
        cls.auth_manager.setup_authentication()

    def write_installation_type(cls) -> None:
        '''
        write or update the installation type into the configuration database
        '''
        
        table_name = 'cow_configuration'
        column_name = 'installation_mode'

        #get cow_configuration table record id
        sql = 'SELECT * FROM {} WHERE 1=1'.format(cls.database.get_tables_dict()[table_name])
        result = cls.database.select_records(sql, 'one')

        #Update database values with installation type
        if isinstance(result, tuple):
            #If a record already exists in the CostMinimizer database
            config_id = result[0]
            sql = 'UPDATE "{}" SET "{}" = ? WHERE "config_id" = ?'.format(table_name, column_name)
            cls.database.update_table_value(table_name, 'installation_mode', config_id, cls.installation_type, sql_provided=sql)
        else:
            #If a record DOES NOT exist in the database (fresh install perhaps)
            request = {
                "installation_mode": cls.installation_type
            }
            cls.database.insert_record(request, table_name)

    def write_available_reports_to_database(cls, usertags=False):
        """
        Write all available reports to the database.
        """
        
        cls.report_file_name = cls.internals['internals']['reports']['report_output_name']
        cls.writer = pd.ExcelWriter(cls.config['output_folder'] + cls.report_file_name, engine='xlsxwriter')

        if not cls.arguments_parsed.version:
            reports_result = AvailableReportsCommand(cls.writer).get_all_available_reports()
            cls.reports = reports_result
            cls.report_classes = reports_result
            table_name = 'cow_availablereports'

            #truncate table first
            cls.database.clear_table(table_name)
            
            for report in cls.reports:
                if usertags == False or (report.supports_user_tags(cls) == True and usertags == True):
                    try:
                        long_description = report.long_description(cls)
                    except:
                        long_description = ''

                    try:
                        domain_name = report.domain_name(cls)
                    except:
                        domain_name = ''

                    html_link = ''
                    dante_link = ''
                    
                    request = {
                        'report_name': report.name(cls),
                        'report_description': report.description(cls),
                        'report_provider': report.report_provider(cls),
                        'service_name': report.service_name(cls),
                        'display': report.display_in_menu(cls),
                        'common_name': report.common_name(cls),
                        'long_description': long_description,
                        'domain_name': domain_name,
                        'html_link': html_link,
                        'dante_link': dante_link,
                        'configurable':report.is_report_configurable(cls),
                        'report_parameters' : str(report.get_report_parameters(cls))
                    }
                    cls.database.insert_record(request, table_name)
                
    def automate_launch_cow_cust_configure(cls) -> tuple:
        """
        Automatically configure COW customer settings using current AWS session credentials.
        """
        # retrieve the default credentials of current session
        # Create an STS client
        sts_client = cls.auth_manager.aws_cow_account_boto_session.client('sts')

        account_id = None
        try:
            # Call the get_caller_identity() method
            response = sts_client.get_caller_identity()

            # Get the user ID and account ID from the response
            user_id = response['UserId']
            account_id = response['Account']

            cls.logger.info(f"[green]User ID: {user_id} - Account ID: {account_id}[/green]")
            cls.console.print(f"[green]User ID: {user_id} - Account ID: {account_id}[/green]")

            # Call the get_session_token() method
            session_token = sts_client.get_session_token

            aws_account_configuration = {}
            aws_account_configuration['aws_cow_account'] = account_id
            aws_account_configuration['aws_cow_profile'] = cls.internals['internals']['boto']['default_profile_name']
            aws_account_configuration['sm_secret_name'] = cls.internals['internals']['boto']['default_secret_name']

            cow_authentication = Authentication()

            if not cls.report_output_directory.is_dir():
                if cls.installation_type == 'local_install':
                    #when running in the container we will not be able to create this directory as it lives outside the container
                    #only attempt to make the directory inside a local install
                    cls.report_output_directory.mkdir()
        
            aws_account_configuration['output_folder'] = str(cls.report_output_directory) if cls.report_output_directory else f'/tmp/cow_output_default/'

            #insert account values into database
            cls.insert_automated_configuration(aws_account_configuration)

            #create awscli config profiles file
            cow_authentication.recreate_all_profiles()

            #re-populate cls.config dictionary with account values
            cls._setup_user_configuration()            

        except Exception as e:
            cls.console.print(f"[red]Error: {e}[/red]")
            cls.console.print(f"[red]Launch 'aws configure' or set values for credentials variables AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY[/red]")
            raise(e)

        return account_id
        
    def insert_automated_configuration(cls, configuration) -> None:
        """
        Insert automated configuration into the database.
        """
        '''
        insert automated configuration
        '''
        #update cow_configuration database table
        try:
            cls.update_cow_configuration_record(configuration)
        except Exception as e:
            msg = f'ERROR: {e} - failed to update configuration database.'
            cls.logger.info(msg)
            raise ErrorInConfigureCowInsertDB(msg)
        
    def update_cow_configuration_record(cls, config):
        """
        Update the COW configuration record in the database.
        """
        request = {}
        table_name = "cow_configuration"
        for i in list(config.items()):
            request[i[0]] = i[1]
        
        # check if table cow_configuration is empty
        l_config = cls.database.get_cow_configuration()
        if len(l_config) == 0:
            cls.database.clear_table(table_name)
            cls.database.insert_record(request, table_name)
        else:
            where = f"config_id = {l_config[0][0]}"
            cls.database.update_record(request, table_name, where)
        
    def get_internals_config(cls) -> dict:
        cls.logger.info(f'cow internals configuration {cls.internals}')
        return cls.internals
        
    def get_regions(cls, excludedRegions=[], selected_accounts=[]) -> list:
        """
        Return a list of AWS regions, potentially filtered by excluded regions and selected accounts.
        """
        '''return regions list'''

        if hasattr(cls, 'regions') and isinstance(cls.regions, list) and len(cls.regions) > 0:
            cls.logger.info(f'Region discovery requested and returned {len(cls.regions)} regions.')

            tmpList = {}

            #Sum up the spend for the regions.
            for i in cls.regions:
                if len(selected_accounts) == 0 or i['account'] in selected_accounts:
                    if i['region'] in tmpList:
                        tmpList[i['region']] += int(i['spend'])
                    else:
                        tmpList[i['region']] = int(i['spend'])

            maxRegionLength = 0

            for r in tmpList.keys():
                maxRegionLength = max(maxRegionLength, len(r))

            regions = []

            for k,v in tmpList.items():
                regions.append(f'{str(k).ljust(maxRegionLength, " ")} : ${v}')

                #regions = cls.regions
        else:
            regions =  [
                'af-south-1',
                'ap-east-1',
                'ap-northeast-1',
                'ap-northeast-2',
                'ap-northeast-3',
                'ap-south-1',
                'ap-south-2',
                'ap-southeast-1', 
                'ap-southeast-2',
                'ap-southeast-3',
                'ap-southeast-4',
                'ca-central-1',
                'eu-central-1',
                'eu-central-2',
                'eu-north-1',
                'eu-south-1',
                'eu-south-2',
                'eu-west-1',
                'eu-west-2',
                'eu-west-3',
                'global',
                'me-central-1',
                'me-south-1',
                'sa-east-1',
                'us-east-1', 
                'us-east-2', 
                'us-west-1', 
                'us-west-2',
                'us-gov-east-1',
                'us-gov-west-1'
                ]
            
            cls.logger.info(f'Region discovery requested and returned {len(regions)} regions.')

        return [r for r in regions if r not in excludedRegions]
            
    def get_client(cls, client_name:str, region_name:str=None):
        '''return boto client '''
        if region_name: 
            return cls.auth_manager.aws_cow_account_boto_session.client(client_name, region_name)
        else:
            return cls.auth_manager.aws_cow_account_boto_session.client(client_name, 'us-east-1')

    
    def get_cache_settings(cls) -> dict:
        '''return cache settings from database'''
        # TODO: Implement cache settings retrieval from database
        cache_settings = ''
        
        return cache_settings

    def validate_database_configuration(self) -> bool:
        """
        Validate the database configuration.

        :return: True if the configuration is valid, False otherwise
        """
        '''validate configuration table has entry in the database'''
        if 'configure' not in self.arguments_parsed:
            if len(self.internals) == 0:
                return False

        return True

    def handle_missing_configuration(self) -> None:
        message = 'CostMinimizer configuration does not exist. Run CostMinimizer --configure and select option 1.'
        self.logger.info(message)
        print(message)
        sys.exit(0)
