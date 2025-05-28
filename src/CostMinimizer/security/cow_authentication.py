# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

__dot_aws_folder__ = '.aws'
from ..constants import __tooling_name__

import os
import sys
import boto3
import shlex
import logging
from pathlib import Path
import subprocess
import datetime
from typing import Optional
from ..config.database import ToolingDatabase
from ..error.error import AuthenticationError

class UnableToRunAccountCredentialsDiscovery(Exception):
    def __init__(self, message="Account discovery error"):
        self.message = message
        super().__init__(self.message)

class UnableToWriteToAWSConfigFile(Exception):
    pass

class AuthenticationManager:
    """Manages AWS authentication and session handling"""
    def __init__(self):
        self.cow_authentication = None
        self.aws_cow_account_boto_session = None
        from ..config.config import Config
        self.config = Config()
        self.logger = logging.getLogger(__name__)

    def get_region_from_cli_agrument(self) -> str:
        return self.config.arguments_parsed.region
    
    def get_region_from_profiles(self) -> str:
        return self.aws_cow_account_boto_session.region_name
    
    def determine_region(self) -> str:
        '''determine region from cli or profile information'''
        if self.config.arguments_parsed.region:
            return self.config.arguments_parsed.region #prefer cli argument
        elif self.aws_cow_account_boto_session.region_name:
            return self.aws_cow_account_boto_session.region_name
        else:
            return None
    
    def setup_authentication(self) -> None:
        if not self.config.arguments_parsed.version:
            self.cow_authentication = Authentication()
            self.aws_cow_account_boto_session = self.configure_boto_session()

            self.config.selected_regions = self.determine_region()
            self.config.selected_region = self.config.selected_regions

            if not self.aws_cow_account_boto_session: 
                self.cow_authentication.recreate_all_profiles()

            if self.config.mode == 'cli':
                self.handle_cli_authentication()

            if not self.test_boto_session():
                sys.exit()

    def test_boto_session(self) -> bool:
        try:
            sts = self.aws_cow_account_boto_session.client('sts')
            sts.get_caller_identity()
            return True
        except Exception as e:
            self.logger.error(f"Authentication Error: {str(e)}")
            self.config.console.print(f'\n[red]\nAuthentication Error: {str(e)}[/red]')
            return False
            
    
    def configure_boto_session(self) -> Optional[boto3.Session]:
        try:
            session = self.cow_authentication.create_account_session()
            if session:
                self.cow_authentication.log_session_access_key(session)
            return session
        except boto3.exceptions.Boto3Error as e:
            self.logger.error(f"Failed to configure boto session: {str(e)}")
            return None

    def handle_cli_authentication(self) -> None:
        login_type = 'aws_profile' #Todo this should come from configuration

        self.cow_authentication.update_login_history(login_type)

class Authentication:

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.config_filename = Path.home() / __dot_aws_folder__ / f'{__tooling_name__}_config'
        self.container_install_config_filename = Path('/tmp/aws/config')

        from ..config.config import Config
        from ..error.alerts import AlertState
        self.appConfig = Config()
        self.alerts = AlertState()

        self.set_aws_config_file_osenviron()

    def set_aws_config_file_osenviron(self, config_filename:Path = None) -> None: 
        '''setup environment variable'''
        if config_filename is None:
            config_filename = self.config_filename

        if 'installation_mode' in self.appConfig.config:
            if  self.appConfig.config['installation_mode'] in ('container_install'):
                config_filename = self.container_install_config_filename

        if not self.appConfig.arguments_parsed.profile:
            os.environ['AWS_CONFIG_FILE'] = str(config_filename)

    def create_cow_awscli_config_directory_path(self, file_path:Path) -> None: 
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        except:
            raise

    def create_cow_awscli_config(self, config_filename:Path = None) -> None: 
        '''Create a config file to use only with Cost Optimization Tooling'''

        if config_filename is None:
            config_filename = self.config_filename

        self.create_cow_awscli_config_directory_path(config_filename)

        try:
            config_filename.touch(exist_ok=True)
        except:
            raise

    def remove_cow_awscli_config(self, config_filename:Path = None) -> None: 

        if config_filename is None:
            config_filename = self.config_filename

        try:
            config_filename.unlink()
        except FileNotFoundError:
            pass
        except:
            raise

    def create_account_session(self, profile_name:str = None, aws_cow_account_boto_session:boto3.Session = None) -> boto3.Session: 
        '''Create default session to use with various calls such as pricing API'''

        if profile_name is None and not self.appConfig.arguments_parsed.profile:
            profile_name = f"{self.appConfig.internals['internals']['boto']['default_profile_name']}_profile"

        if self.appConfig.arguments_parsed.profile:
            profile_name = self.appConfig.arguments_parsed.profile

        try:
            aws_cow_account_boto_session = boto3.Session(profile_name=profile_name)
            
            return aws_cow_account_boto_session
        except Exception as e:
            message = f"boto3.session is not using credentials from profile {profile_name} since not present !"
            self.alerts.alerts[profile_name] = message
            self.logger.info(message)

        try:
            aws_cow_account_boto_session = boto3.Session()
            return aws_cow_account_boto_session
        except Exception as e:
            message = f"boto3.session is not using credentials from profile {profile_name} since not present !"
            self.alerts.alerts[profile_name] = message
            self.logger.info(message)
            sys.exit(0)

    def log_session_access_key(self, session) -> None: 
        '''log the access key used by the session'''
        try:
            if isinstance(session, boto3.session.Session):
                self.logger.info(f'Using access key {session.get_credentials().access_key} for session {session.profile_name}')
                self.appConfig.console.print(f'Using access key [green]{session.get_credentials().access_key}[/green] for session [green]{session.profile_name}[/green]')
        except:
            self.logger.info(f'Unable to log access key for session.')

    def check_aws_cow_account_name( self, config) -> int:
        '''check if capital Admin profile exists and throw error if it's missing'''
        try:
            command = "aws sts get-caller-identity"
            account_output = subprocess.run(shlex.split(command), capture_output=True)
        except Exception as e:
            print(e)
            if self.appConfig.mode == 'cli':
                raise AuthenticationError(e,self.appConfig.mode)

        if not account_output.returncode:
            for line in account_output.stdout.decode('ascii').splitlines():
                if '"Account":' in line:
                    line = line.replace(" ","")
                    #account_number = line.split(':')
                    return 0

        e = Exception()
        errorTuple = (str(account_output.stderr),)
        e.args += errorTuple
        if self.appConfig.mode == 'cli':
            raise AuthenticationError(e,self.appConfig.mode)

        return 1

    def write_awscli_config_profile(self, config_profile:str, customer_name:str, config_filename:str = None) -> None:
        '''write profile configuration to disk'''

        if config_filename is None:
            config_filename = str(self.config_filename)

        # add new to the CostMinimizer specific profile file
        try:
            with open(config_filename, "r") as f:
                if f'{customer_name}_profile' in f.read():
                    print(f'Config file {config_filename} already contains profile {customer_name}_profile')
                else:
                    # Append-adds at last
                    with open(config_filename, "a") as f:
                        f.write(config_profile)
                        f.close()
        except:
            msg = f'Unable to write profile to file {config_filename}'
            self.logger.info(msg)
            raise UnableToWriteToAWSConfigFile(msg)

    def create_authentication_profile(self, name:str, account_number:str, region:str, role:str, email_address:str = None, config_filename:Path = None) -> None: 
        '''abstraction - get, create and write the awscli profile'''
        if email_address is None:
            email_address = '' #self.get_account_email_address(account_number)

        config_profile = '' #self.get_awscli_config_profile(name, region, email_address, role)

        #self.write_awscli_config_profile(config_profile, name, str(config_filename))

    def recreate_all_profiles(self, config_filename:Path = None) -> None: 
        try:
            if config_filename is None:
                if self.appConfig.config.get('installation_mode') in ('container_install'):
                    config_filename = self.container_install_config_filename
                else:
                    config_filename = self.config_filename

            self.remove_cow_awscli_config(config_filename)
            self.create_cow_awscli_config(config_filename)

            #get all customer profiles from database
            cow_database = ToolingDatabase()
            customers = cow_database.get_all_customers()

            #write customer profiles
            if len(customers) > 0:
                customer_profile_role = self.appConfig.internals['internals']['cur_customer_discovery']['role']
                for customer in customers:
                    try:
                        self.create_authentication_profile(customer.Name, customer.PayerAccount, customer.CurRegion, customer_profile_role, customer.EmailAddress, config_filename)
                    except Exception as e:
                        self.logger.error(f"Failed to create authentication profile for customer {customer.Name}: {str(e)}")

            #get configuration from database
            configuration = cow_database.get_configuration()

            #write profile
            if len(configuration) > 0:
                if configuration[0][1] != None:
                    self.create_authentication_profile(
                        configuration[0][2],
                        str(configuration[0][1]),
                        self.appConfig.internals['internals']['boto']['default_region'],
                        self.appConfig.internals['internals']['boto']['default_profile_role'],
                        None,
                        config_filename
                        )
                else:
                    e = Exception()
                    errorTuple = ("No aws account",)
                    e.args += errorTuple
                    sys.exit(1)
        except Exception as e:
            self.logger.error(f"Failed to recreate all profiles: {str(e)}")
            raise

    def validate_account_credentials(self, profile_name:str, customer_name:str = None) -> bool:
        account_list =[]
        account_list.append(self.appConfig.config['aws_cow_account'])

        try:
            self.check_aws_cow_account_name(account_list)
        except Exception as e:
            return False

        s = self.create_account_session(profile_name)

        if isinstance(s, boto3.session.Session):
            try:
                c = s.client('sts')
                c.get_caller_identity()
            except Exception as e:
                print(f"Unable to validate credentials for profile {profile_name} with boto sts.")
                #retry after validation
                self.alerts.alerts[profile_name] = f"Unable to validate credentials for profile {profile_name} with boto sts."
                return False

            return True

        return False

    def validate_role_can_poll_secrets_manager(self, profile_name:str, service_name='secretsmanager') -> bool: 

        s = self.create_account_session(profile_name)

        if isinstance(s, boto3.session.Session):
            try:
                c = s.client('sts')
                identity = c.get_caller_identity()
            except:
                self.alerts.alerts[profile_name] = f"Unable to validate credentials for profile {profile_name} with boto sts."
                return False

            role_name = identity['Arn'].split('/')[1]

            try:
                c = s.client(service_name)
                if service_name == 'secretsmanager': 
                    response = c.list_secrets()['ResponseMetadata']['HTTPStatusCode']
                elif service_name == 'athena':
                    response = c.list_data_catalogs()['ResponseMetadata']['HTTPStatusCode']
            except:
                self.alerts.alerts[profile_name] = f"Unable to validate role can access admin account."
                return False


            return [role_name, response]



        return False

    def update_login_history(self, login_type) -> None: 
        '''
        update login history in database
        login_type: midway 
        login_timestamp: datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        login_cache_expiration: datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        '''

        if login_type == 'aws_profile':
            login_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            login_cache_expiration = ''
            login_hash = ''
        else:
            raise ValueError('Internal Error: invalid login type provided')

        self.appConfig.database.insert_record({'login_type': login_type, 'login_timestamp': login_timestamp, 'login_cache_expiration': login_cache_expiration, 'login_hash': login_hash}, 'cow_login')
