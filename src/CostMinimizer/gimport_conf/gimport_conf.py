# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import sys
import os
from pathlib import Path
import yaml
import datetime
import logging

from ..utils.yaml_loader import import_yaml_file

DEFAULT_dump_global_config = f'/dump_global_config_{__tooling_name__}.yaml'

class ErrorInConfigureCowInsertDB(Exception):
    pass

class CowImportConf:

    def __init__(self, appConfig) -> None:
        self.logger = logging.getLogger(__name__)
        from ..config.config import Config
        self.appConfig = Config()
        self.app_path = Path(os.path.dirname(__file__))
        
        internals_file = self.app_path.parent / f'conf/{__tooling_name__}_internals.yaml'

        if internals_file.is_file():
            cow_internals = import_yaml_file(internals_file)
        else:
            self.appConfig.console.print(f'[orange]Unable to find {__tooling_name__}_internals file to determine version. Looking in {internals_file}')

        #determine if configuration exists in the db
        if not self.validate_database_configuration():
            self.logger.info(f'CostMinimizer configuration file does not exist.  Run "CostMinimizer --configure" and select option 1.')
            self.appConfig.console.print(f'[red]CostMinimizer configuration file does not exist.  Run "CostMinimizer --configure" and select option 1.')
            sys.exit()


    def run(self):
        self.import_dump_global_configuration()
    
    
    def import_dump_global_configuration(self):
            
        try:
            l_dump_filename = str(self.appConfig.default_report_request.parent) + DEFAULT_dump_global_config
            with open(l_dump_filename, 'r') as yaml_file:
                yaml_data = yaml.safe_load(yaml_file)
        except:
            self.console.print(f"[red]YAML dump file cannot be opened: {l_dump_filename} !")
            return
        
        try:
            
            configuration = yaml_data['aws_account']
            self.insert_automated_configuration(configuration)
            
            l_date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if (self.appConfig.config['aws_cow_account'] is not None): 
                # JSR TODO Update this to use the database method
                self.appConfig.database.clear_table("cow_customerdefinition")
                self.appConfig.database.clear_table("cow_customerpayeraccounts")
            
            self.appConfig.console.print(f"[green]YAML global configuration file {l_dump_filename} successfully imported !\n")
            self.appConfig.console.print(yaml.dump(yaml_data))
        except Exception as e:
            self.appConfig.console.print(f"[red]YAML dump file {l_dump_filename} exists but cannot be imported into database !")
            return

    def validate_database_configuration(self) -> bool:
        '''
        Check if configuration exists in the database
        '''
        try:
            # Check if cow_configuration table has any records
            config = self.appConfig.database.get_cow_configuration()
            return len(config) > 0
        except Exception as e:
            self.logger.error(f"Error validating database configuration: {e}")
            return False
            
    def insert_automated_configuration(self, configuration) -> None:
        '''
        insert automated configuration
        '''
        #update cow_configuration database table
        try:
            self.update_cow_configuration_record(configuration)
        except Exception as e:
            msg = f'ERROR: failed to insert CostMinimizer configuration into database.'
            self.logger.info(msg)
            raise ErrorInConfigureCowInsertDB(msg)

    def update_cow_configuration_record(self, config):
        request = {}
        for i in list(config.items()):
            request[i[0]] = i[1]

        table_name = "cow_configuration"
        self.appConfig.database.clear_table(table_name)
        self.appConfig.database.insert_record(request, table_name)