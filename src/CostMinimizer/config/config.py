# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

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
from pathlib import Path
from ..patterns.singleton import Singleton
from rich.console import Console
import pandas as pd

from ..security.cow_authentication import Authentication
from ..commands.available_reports import AvailableReportsCommand
from ..version.version import ToolingVersion
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
        
        '''Auto discovery of dynamic configuration parameters'''
        #Path() of users home directory on the system
        cls.local_home = Path.home()
        #Path of this config class
        cls.config_class_path = Path(os.path.dirname(__file__))
        #Path() of application business logic
        cls.app_path = cls.config_class_path.parent 
        #Path() of installation directory
        cls.install_dir = Path.cwd()
        #Path() of application root directory
        cls.conf_dir = cls.app_path / 'conf'
        cls.console = Console()
        cls.cur_db_arguments_parsed = None
        cls.cur_table_arguments_parsed = None

        #Set CM Internals YAML File
        cls.internals, cls.origin_internals_values = cls.__load_cow_config(
          config_file=cls.conf_dir / "cow_internals.yaml") #TODO need to change this filename

        #set installation type; if container_deployment_file exists on the system
        #then the installation type is container
        cls.container_deployment_file = cls.conf_dir / "container.txt"
        cls.installation_type = cls.__set_installation_type()
        #set report directory
        cls.report_directory = cls.__set_report_directory(cls.installation_type)

        cls.selected_regions = ['us-east-1']

    def setup(cls):
        '''setup the cow database and user configuration'''
        try:
            if os.getenv('APP_CM_USER_HOME_DIR'):
                cls.container_host_system_home = Path(os.getenv('APP_CM_USER_HOME_DIR'))
            else:
                cls.container_host_system_home = cls.local_home
            
            #set report_output_directory; this differs in container vs local install
            if cls.installation_type == 'container_install':
                #inside the container this should map to the host system $HOME/cow as discoverd by the env far
                cls.report_output_directory = cls.container_host_system_home / cls.internals['internals']['reports']['report_output_directory']
            else:
                cls.report_output_directory = cls.local_home / cls.internals['internals']['reports']['report_output_directory']
            
            cls._setup_database(cls)
            cls.write_installation_type()
            cls._setup_user_configuration()
            cls._setup_internals_parameters()
        except Exception as e:
            cls.logger.error(f"Error during setup: {str(e)}")
            raise


    def __setup_default_internals_paramaters(cls) -> str:
        '''setup the default internals parameters'''

        internals_yaml_defaults = """
internals:
  db_fields_to_update:
    - version
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
  version: 0.0.1
"""
        return internals_yaml_defaults
    
    def _setup_database(cls, config):
        """Create database and all tables if needed"""
        cls.database = ToolingDatabase()

        #process table schema updates
        cls.database.process_table_schema_updates()

    def __set_installation_type(cls) -> str:
        '''
        set installation type:

        return values:
        - container_install
        - local_install
        '''

        if Path.is_file(cls.container_deployment_file):
            cls.installation_type = 'container_install'
        else:
            cls.installation_type = 'local_install'

        return cls.installation_type
      
    def __set_report_directory(cls, installation_type: str) -> str:
        '''
        set report directory:

        return values:
        - cow
        - .cow
        '''

        if installation_type == 'container_install':
          #on container the mapping is to /root/.cow inside the container, on local_install it is $HOME/cow
          report_directory = cls.local_home / cls.internals['internals']['reports']['report_output_directory_for_container']
        else:
          #local_install
          report_directory = cls.local_home / cls.internals['internals']['reports']['report_output_directory']

        return report_directory
    
    def __load_cow_config(cls, config_file=None):
        """
        Load COW configuration from a YAML file or use default values.
        """
        if not os.path.exists(config_file):
            cls.logger.info(f"Unable to find internals file: {config_file} (searching for values in the database)")

        try:
            with open(config_file, "r") as stream:  # Attempt to open and read the YAML conf file
                yaml_config = yaml.safe_load(stream)
            origin_internals_values = 'yaml'
        except:
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

        # at this point, the cow_internals contains either yaml file values or default factory from CowConfig class if yaml does not exists
        cow_internals_from_yaml_file_or_defaults = cls.internals 

        #fetch CostMinimizer internals parameters from database if exist
        db_internals_params = cls.database.fetch_internals_parameters_table()

        # Priority of the origin of internals parameters : 
        #   1) DB if exists 
        #   2) yaml file if exists 
        #   3) CowConfig class defaults values

        # if internals parameters exist in the database
        if len(db_internals_params) > 0:
            cls.internals = db_internals_params

            # if internals yaml file exist also
            if (cls.origin_internals_values == 'yaml'):
               
                # force the update of specific fields in the databases like version number
                try:
                    list_of_fields_to_update_in_db = cow_internals_from_yaml_file_or_defaults['internals']['db_fields_to_update']
                    if (len(list_of_fields_to_update_in_db) == 0):
                        list_of_fields_to_update_in_db = ['internals.version']
                except:
                    list_of_fields_to_update_in_db = []

                cls.database.update_internals_parameters_table_from_yaml_file(cow_internals_from_yaml_file_or_defaults, '', list_of_fields_to_update_in_db)
                cls.logger.info(f'Successfully loaded internals parameters from the database & internals yaml file found => Fieds modified: {list_of_fields_to_update_in_db}')
            else:
                cls.logger.info(f'Successfully loaded internals parameters from the database, but internals yaml file not found (no db fields modified)')
                
                # init value of version in ToolingVersion class from value contained in the DB
                ToolingVersion.version = cls.internals['internals']['version']

        # if no paramters are already stored in the database
        else:
            # Db does not contains internals values, so write them
            # cow_internals contains either yaml file values or default factory from CowConfig class if yaml does not exists
            cls.database.write_internals_parameters_table(cls.internals)
            cls.console.print(f'[green]\nSuccessfully write internals parameters from yaml file (or default if not exists) to database ![/green]')

    def write_installation_type(cls):
        """
        Write the determined installation type to the database.
        """
        '''set if the installation is inside of a container'''

        '''
        The container deployment process will put a file 'container.txt' 
        inside the conf directory. If we have this file here, we are inside 
        a container
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
            cls.database.update_table_value(table_name, 'installation_mode', config_id, 'new_value', sql_provided=sql)
        else:
            #If a record DOES NOT exist in the database (fresh install perhaps)
            request = {
                "installation_mode": cls.installation_type
            }
            cls.database.insert_record(request, table_name)
            
    def database_initial_defaults(cls, appInstance, arguments_parsed=None):
        
        if hasattr(arguments_parsed, 'usertags'):
            u_tags = arguments_parsed.usertags
        else:
            u_tags = False

        #write all available reports to database
        cls.write_available_reports_to_database(appInstance, u_tags)
        
    def write_available_reports_to_database(cls, appInstance, usertags=False):
        """
        Write all available reports to the database.
        """

        if (cls.config.get('output_folder') is None):
            cls.console.print(f'No output folder specified in config file. Attempting automatic configuration.')
            
            try:
                cls.automate_launch_cow_cust_configure()

                cls.console.print(f'[green]Automatic configuration successfully performed ![/green]')
                cls.console.print(f'[yellow]WELCOME ! This is the first time CostMinimizer is launched, please configure the tooling !')
                cls.console.print(f'[yellow]        Select the option 1)    Manual CostMinimizer Tool Configuration (setup my AWS account) !!![/yellow]')
                cls.console.print(f'[yellow]        In case you want to use CUR, verify or update the values of cur_db & cur_table"[/yellow]')
                ConfigureToolingCommand(cls.auth_manager.appInstance).run()

            except Exception as e:
                cls.console.print(f'[red]Error during initial configuration. Please run [bold]"CostMinimizer --configure"[/bold] to configure your account.[/red]')
                sys.exit(0)
        
        cls.report_file_name = cls.internals['internals']['reports']['report_output_name']
        cls.writer = pd.ExcelWriter(cls.config['output_folder'] + cls.report_file_name, engine='xlsxwriter')

        if not appInstance.config_manager.appConfig.arguments_parsed.version:
            cls.reports = AvailableReportsCommand(appInstance, cls.writer).get_all_available_reports()
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
                
    # retrieve the default credentials of current session
    def automate_launch_cow_cust_configure(cls) -> tuple:
        """
        Automatically configure COW customer settings using current AWS session credentials.
        """
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
            
    def get_cache_settings(cls) -> dict:
        '''return cache settings from database'''
        # TODO: Implement cache settings retrieval from database
        cache_settings = ''
        
        return cache_settings
        
    # For backward compatibility with code expecting a CowConfig instance  
    class CowConfigWrapper:
        def __init__(self, cm_config_instance):
            self.appConfig = cm_config_instance
            
    def get_cow_config_wrapper(cls):
        """Returns a CowConfig-compatible wrapper around this instance"""
        return cls.CowConfigWrapper(cls)