
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__
from ..config.config import Config
import sqlparse

class ResourceDiscoveryController:
    '''
    The resource discovery controller is responsible for discovering specific 
    resources from either CUR or API calls into the account(s)
    '''
    def __init__(self) -> None:
        self.appConfig = Config()
        self.logger = self.appConfig.logger
        self.cur_type = None
        self.resource_id_column_exists = False
        self.precondition_reports = {'cur_preconditionavginstancecost.cur': True}

    def check_column_exists(self, list_to_scan, column_name):
        """Check if a column exists in the list of columns contained in list_to_scan.
        
        Args:
            list_to_scan: list of columns return by show table Athena
            column_name: Name of the column to check
            
        Returns:
            bool: True if column exists, False otherwise
        """
        self.resource_id_column_exists = False
        try:
            # Check if a column exists in the list of columns contained in list_to_scan
            response = [row for row in list_to_scan if row['Data'][0]['VarCharValue'].strip() == column_name]

            # If we got results (more than just the header row), the column exists
            if len(response) < 1:
                return False
            else:
                self.resource_id_column_exists = True
                return True
            
        except Exception as e:
            self.logger.warning(f"Error checking if column {column_name} exists: {str(e)}")
            # If there's an error, assume the column doesn't exist to be safe
            return False

    def determine_cur_report_type(self,cur_provider) -> str:
        '''
        Determine the CUR report type based column names
        '''
        athena_client = self.appConfig.get_client('athena', region_name=self.appConfig.default_selected_region)
        
        #This is not the best way to get to the run_athena_query function; perhaps restructure this in future
        report = cur_provider.import_reports()[0](self.appConfig)
        
        # "coast-data-export-focus-6c77d700"."coast-focus"
        SQL = f"show columns from `{cur_provider.cur_table.strip()}`;"
        
        try:
            result = report.run_athena_query(athena_client, SQL, self.appConfig.config['cur_s3_bucket'], cur_provider.cur_db.strip())
        except Exception as e:
            self.logger.error(f'Unable to determine CUR report type: {str(e)}')
            raise Exception(f'Unable to determine CUR report type: {str(e)} \n Please verify the tooling configuration !')
        
        # from the list of columns names, verify if line_item_resource_id exists
        self.resource_id_column_exists = self.check_column_exists( result, 'line_item_resource_id')
        self.logger.info(f'Using Athena, verify if line_item_resource_id exists: {self.resource_id_column_exists}')
        self.appConfig.console.print(f'Is line_item_resource_id columns is present in the CUR table ? {self.resource_id_column_exists}')

        # scan result to descover the type of CUR
        l_type_of_CUR = 'Unknown'
        for row in result:
            if row['Data'][0]['VarCharValue'].strip() == 'product_instance_type_family':
                l_type_of_CUR = 'legacy'
                break
            if row['Data'][0]['VarCharValue'].strip() == 'product':
                l_type_of_CUR = 'v2.0'
                break
            if row['Data'][0]['VarCharValue'].strip() == 'contractedunitprice ':
                l_type_of_CUR = 'focus'
                break
        
        self.logger.info(f'Using Athena, get the type of CUR: {l_type_of_CUR}')
        self.appConfig.console.print(f'Reading Athena, the type of CUR is: {l_type_of_CUR}')
        return l_type_of_CUR


    def run(self, report_controller):
        '''
        TODO currently only CUR is supported as a precondition report.  Eventually
        we will want to support all providers
        '''
        
        providers = report_controller.get_report_providers()
        
        if 'cur_reports' in providers:
            cur_provider = report_controller.import_provider('cur_reports')(self.appConfig)

        self.appConfig.console.print('[green]Running Cost & Usage Report: Resource Discovery (Precondition) Reports')

        cur_provider.setup()
        
        self.cur_type = self.determine_cur_report_type(cur_provider)
        
        self.precondition_reports_in_progress = cur_provider.run(additional_input_data = 'preconditioned')


    




    

    