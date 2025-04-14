# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import yaml
import logging
from pathlib import Path
import pandas as pd
from ..report_output_handler.report_output_folder_crawler import ReportOutputFolderCrawler
from ..security.cow_encryption import FileEncryptionOperationError


class ReportOutputReportRequestParser:
    '''Parse the report_request.yaml file and return data report statistics'''


    def __init__(self, appConfig, report_name, file_parent_dir_structure=None) -> None:
        self.appConfig = appConfig
        self.logger = logging.getLogger(__name__)
        self.report_name = report_name
        self.rofc = ReportOutputFolderCrawler(self.appConfig)
        self.report_request = None #place holder for imported yaml file
        self.report_request_state = None

#        print(self.rofc.report_directory)

        if Path(self.rofc.report_directory / report_name / self.rofc.encrypted_report_request_file).is_file():
            self.report_request_state = 'encrypted'
            self.report_request_absolute_path = Path(self.rofc.report_directory / report_name / self.rofc.encrypted_report_request_file)
        elif Path(self.rofc.report_directory / report_name / self.rofc.decrypted_report_request_file).is_file():
            self.report_request_state = 'decrypted'
            self.report_request_absolute_path = Path(self.rofc.report_directory / report_name / self.rofc.decrypted_report_request_file)
        elif Path(self.rofc.report_directory / report_name / self.rofc.report_request_file).is_file():
            self.report_request_state = 'plain'
            self.report_request_absolute_path = Path(self.rofc.report_directory / report_name / self.rofc.report_request_file)
        else:
            self.report_request_state = 'missing'
            self.report_request_absolute_path = Path('/some/fake/file/path.yaml')

#        print(self.report_request_state)
#        print('Got here')

        self.import_report_request_file()

#        print('Got here 2')

        self.customer_name = self.get_customer_name_from_report_request()

    def validate_report_request_file_exists(self) -> bool:
        '''validate if report request exists'''
        return self.report_request_absolute_path.is_file()

    def validate_report_request(self) -> bool:
        '''validate if report request exists'''
        
        #validate file exists
        if not self.validate_report_request_file_exists():
            return False

        #validate imported file is a dict
        if isinstance(self.report_request, dict):

            #validate file has 'customers' attribute
            if 'customers' not in self.report_request:
                return False
            else:
                for customer_name in self.report_request['customers'].keys():
                    if 'accounts' not in self.report_request['customers'][customer_name]:
                        return False
                        break
                    if 'regions' not in self.report_request['customers'][customer_name]:
                        return False
                        break

            if 'reports' not in self.report_request:
                return False
            
        else:
            return False
        
        return True
    
    def get_date_from_folder_name(self, folder_name) -> str:
        '''return date from folder name'''
        f = folder_name.split('-')
        d = '-'.join(f[1:])
        return d
    
    def import_report_request_file(self) -> Path:
        '''import rr file and return Path instance'''
        if self.validate_report_request_file_exists():

            #if encrypted, decrypt first and then read in file
            if self.rofc.is_report_request_encrypted(self.report_name):
                self.logger.info('Report request is encrypted, decrypting...')
                try:
                    self.appConfig.encryption.decrypt_file(self.report_request_absolute_path, rename=True)
                except FileEncryptionOperationError as e:
                    self.logger.error(f'Failed to decrypt report request file {self.report_request_absolute_path}')
                    self.logger.exception(e)
                    raise FileEncryptionOperationError(f'Unable to decrypt {self.report_request_absolute_path}')
                except:
                    raise
                
                
                if Path(self.rofc.report_directory / self.report_name / self.rofc.decrypted_report_request_file).is_file():
                    self.report_request_absolute_path = Path(self.rofc.report_directory / self.report_name / self.rofc.decrypted_report_request_file)
                    self.report_request_state = 'decrypted'
                    
            with open(self.report_request_absolute_path, 'r') as f:
                self.report_request = yaml.safe_load(f)

            self.appConfig.encryption.encrypt_file(self.report_request_absolute_path, rename=True)
            self.report_request_state = 'encrypted'
            self.report_request_absolute_path = Path(self.rofc.report_directory / self.report_name / self.rofc.encrypted_report_request_file)

    def import_excel_report_file(self, report_name, sheet_name='Estimated savings'):
        '''import excel file, default '''
        excel_file = Path(self.rofc.report_directory) / report_name / self.rofc.get_output_report_name()

        if excel_file.is_file():
            return pd.read_excel(excel_file, sheet_name=sheet_name)
        
        return {}

    def generate_report_request_hash(self) -> str:
        '''generate a hash of the report request contents'''
        pass

    def generate_report_request_account_hash(self) -> str:
        '''generate a hash of the report request accounts '''
        pass

    def generate_report_request_region_hash(self) -> str:
        '''generate a hash of the report request regions '''
        pass

    def generate_report_request_reports_hash(self) -> str:
        '''generate a hash of the report request regions '''
        pass
        
    def get_customer_name_from_report_request(self) -> str:
        '''get the customer name in the report request file'''
        if self.validate_report_request():
            for customer,values in self.report_request['customers'].items():
                return customer
        
        return None
    
    def get_account_count(self) -> str:
        '''get a count of the number of accounts in the report request'''
        if self.validate_report_request():
            return len(self.report_request['customers'][self.customer_name]['accounts'])
    
        return '0'
    
    def get_region_count(self) -> str:
        '''get a count of the number of accounts in the report request'''
        if self.validate_report_request():
            return len(self.report_request['customers'][self.customer_name]['regions'])

        return '0'
    
    def get_report_count(self) -> str:
        '''get a count of the number of accounts in the report request'''
        if self.validate_report_request():
            return len(self.report_request['reports'])
        
        return '0'
    
    def get_accounts(self) -> list:
        '''get accounts from report request'''
        if self.validate_report_request():
            return self.report_request['customers'][self.customer_name]['accounts']

        return []
        
    def get_regions(self) -> list:
        '''get regions from report request'''
        if self.validate_report_request():
            return self.report_request['customers'][self.customer_name]['regions']
        
        return []
        
    def get_reports(self) -> list:
        '''get reports from report request'''
        if self.validate_report_request():
            reports = []
            for k,v in self.report_request['reports'].items():
                reports.append(k)

            return reports

        return []