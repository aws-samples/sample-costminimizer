# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import os
from ..utils.yaml_loader import import_yaml_file
from pathlib import Path
from ..utils.yaml_loader import dump_configuration_to_file


DEFAULT_dump_global_config = f'/dump_global_config_{__tooling_name__}.yaml'

class CowExportConf:

    def __init__(self, appInstance) -> None:
        #ToDo remove appInstance
        # self.appInstance = appInstance
        from ..config.config import Config
        self.appConfig = Config()
        self.app_path = Path(os.path.dirname(__file__))

        internals_file = self.appConfig.internals_file

        if internals_file.is_file():
            cow_internals = import_yaml_file(internals_file)
        else:
            self.appConfig.console.print(f'[orange]Unable to find {__tooling_name__}_internals file to determine version. Looking in {internals_file}')

        self.version = self.appConfig.internals['internals']['version']


    def run(self):
        self.dump_global_configuration()

    def aws_account_configured_as_dict(self) -> dict:
        '''Return customer configuration for dump'''

        #table_name = 'cow_configuration'        
        aws_account_data = self.appConfig.database.get_cow_configuration()

        l_headers = [
            "config_id",
            "aws_cow_account",
            "aws_cow_profile",
            "sm_secret_name",
            "output_folder",
            "installation_mode",
            "container_mode_home",
            "cur_db",
            "cur_table",
            "cur_region",
            "aws_cow_s3_bucket",
            "ses_send",
            "ses_from",
            "ses_region",
            "ses_smtp",
            "ses_login",
            "ses_password",
            "costexplorer_tags",
            "costexplorer_tags_value_filter",
            "graviton_tags",
            "graviton_tags_value_filter",
            "current_month",
            "day_month",
            "last_month_only",
            "aws_access_key_id",
            "aws_secret_access_key",
            "cur_s3_bucket"
        ]

        dict_zip = dict(zip(l_headers,aws_account_data[0]))
        return dict_zip
    
    def dump_global_configuration(self):

        l_dump_filename = str(self.appConfig.default_report_request.parent) + DEFAULT_dump_global_config

        l_existing_aws_cow_account_conf = {'aws_account' : dict(self.aws_account_configured_as_dict())}

        l_all_customer_data = {'customers': dict(self.aws_customers_configured_as_dict())} #TODO we do not need this in CM implementation

        l_existing_aws_cow_account_conf.update( dict(l_all_customer_data))
        
        if self.appConfig.arguments_parsed.ls_conf:
            self.appConfig.console.print(f'[green]YAML global configuration: {l_dump_filename} \n')
            self.appConfig.console.print(l_existing_aws_cow_account_conf)
            self.appConfig.console.print(f'\n[green]Internals Configruation: \n')
            self.appConfig.console.print(self.appConfig.internals)
            return
        elif self.appConfig.arguments_parsed.dump_configuration:
            if dump_configuration_to_file(l_dump_filename, l_existing_aws_cow_account_conf):
                self.appConfig.console.print(f"[green]YAML global configuration successfully dumped: {l_dump_filename} !\n")
                self.appConfig.console.print(l_existing_aws_cow_account_conf)
            return
                     
    def aws_customers_configured_as_dict(self) -> dict:
        '''Return customer configuration for dump'''

        #table_name = 'cow_customerdefinition'

        all_customer_data = self.appConfig.database.get_all_customers()
        # now payer in different table

        l_headers = [
                "cx_id",
                "cx_name",
                "email_address",
                "create_time",
                "last_used_time",
                "aws_profile",
                "secrets_aws_profile",
                "athena_s3_buckt",
                "cur_db_name",
                "cur_db_table",
                "cur_region",
                "min_spend",
                "acc_regex",
                "account_email",
                "payer_id"]

        dict_zip = {}
        for cx in all_customer_data:
            cx_list = list(cx._row)
            cx_list.append(cx.PayerAccount)
            dict_zip[cx.Name] = dict(zip(l_headers,cx_list))

        return dict_zip