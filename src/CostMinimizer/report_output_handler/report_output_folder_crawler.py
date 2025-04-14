# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import os
import re
from datetime import datetime
from pathlib import Path

class ReportOutputFolderCrawler:

    def __init__(self, appConfig) -> None:
        self.appConfig = appConfig
        self.config = appConfig.config
        #if running inside a container
        if self.appConfig.installation_type in ('container_install'):
            self.report_directory = Path(self.appConfig.config['container_mode_home'])
            if self.appConfig.config['output_folder'] is None:
                self.report_directory_for_ui = self.config.report_output_directory #place holder
            else:
                self.report_directory_for_ui = self.config.report_output_directory
        else:
            #local install both write dest and ui should be the same
            self.report_directory = self.config.report_output_directory
            self.report_directory_for_ui = self.config.report_output_directory


        self.filesystem_report_directory = self.report_directory
        self.filesystem_report_directory_for_ui = self.report_directory_for_ui
        self.report_request_file = self.config.internals['internals']['reports']['default_report_request']
        self.encrypted_report_request_file = self.config.internals['internals']['reports']['default_encrypted_report_request']
        self.decrypted_report_request_file = self.config.internals['internals']['reports']['default_decrypted_report_request']
        self.appConfig.report_file_name = self.appConfig.cow_config.get_internals_config()['internals']['reports']['report_output_name']
        self.folder_customer_name = None
        self.folder_datetime = None

        self.get_parsed_report_folder_names()

    def set_output_folder_path(self) -> str:
        '''return the output folder path'''
        if self.appConfig.config['installation_mode'] in ('container_install'):
            output_folder = self.appConfig.config['container_mode_home']
        else:
            output_folder = self.appConfig.config['output_folder']

        return output_folder

    def parse_report_folders_files(self, customer_name=None, path_type='folder'):
        '''return a list of report folders under ending in yyyy-mm-dd-hh-mm'''       
        
        #get a list of all the files in the report directory
        list_of_folder_contents = os.listdir(self.report_directory.resolve())

        if path_type == 'folder':
            #filter out files
            list_of_folders = [ folder for folder in list_of_folder_contents if Path(self.report_directory / folder).is_dir() ]
        else:
            list_of_folders = list_of_folder_contents
        
        #sort by ctime so we have the latest ones last
        list_of_files = sorted(
            list_of_folders,
            key = lambda x: os.path.getctime(os.path.join(self.report_directory.resolve(), x))
            )
        parsed_folders = []

        if customer_name is None:
            for folder in list_of_files:
                #look for 'YYYY-M' signature in the file name
                #TODO need to make this better - if any one puts another file with YYYY it will break this
                if isinstance(re.search('202\d-\d+', folder), re.Match):
                    parsed_folders.append(folder)
        else:
            for folder in list_of_files:
                pattern = fr'{customer_name}-202\d-\d+'
                if isinstance(re.search(pattern, folder), re.Match):
                    parsed_folders.append(folder)

        return parsed_folders

    def parse_output_folder_name(self, folder) -> dict:
        '''return dictionary with the available report folders in this format
        {
            'customer_name': beginning_part_of_folder_containing_name
            'datestamp': the_date_stamp_part_of_folder_name_as_datetime_object
            'report_folder_name': constructed report folder name in format of 'customer_name'-YYYY-MM-DD-HH-MM
        }
        
        '''
        
        customer_name = []
        date_signature = []
        found_start_of_date=False

        for string in folder.split('-'):
            #look for 2022 or 2023 etc... 
            if ''.join(list(string)[:3]) == '202':
                date_signature.append(int(string))
                found_start_of_date=True
            elif found_start_of_date:
                date_signature.append(int(string))
            else:
                customer_name.append(string)

        folder_datetime = datetime(*date_signature)
        folder_customer_name = '-'.join(customer_name)
        folder_name = f'{folder_customer_name}-{folder_datetime.year}-{folder_datetime.strftime("%m")}-{folder_datetime.strftime("%d")}-{folder_datetime.strftime("%H")}-{folder_datetime.strftime("%M")}'
        
        return {'customer_name': folder_customer_name, 'datestamp': folder_datetime, 'folder_name': folder_name }

    def get_parsed_report_folder_names(self) -> list:
        '''return a list of dictionairies containing folder metadata''' 
        parsed_report_folder_list = self.parse_report_folders_files()
        folder_list = []

        for folder in parsed_report_folder_list:
            folder_list.append(self.parse_output_folder_name(folder))

        return folder_list

    def get_output_report_name(self) -> str:
        '''return the name of the main xls report file'''
        return self.appConfig.report_file_name
    
    def get_csv_files(self, report_absolute_directory) -> list:
        '''return a list of validated csv files in a report folder'''

        csv_directory = Path(report_absolute_directory)  / 'csv'

        if csv_directory.is_dir():
            return os.listdir(csv_directory.resolve())
        
        return []
    
    def get_error_logs(self, report_absolute_directory) -> list:
        '''return a list of validated log files in a report folder'''
        
        log_directory = Path(report_absolute_directory)  / 'logs'

        if log_directory.is_dir():
            return os.listdir(log_directory.resolve())
        
        return []

    def is_report_request_encrypted(self, parent_folder:str) -> bool:
        '''return true if report_request.yaml is encrypted'''
        output_dir = self.set_output_folder_path()

        report_request_file = Path(output_dir + '/' + parent_folder + '/' + self.report_request_file)
        report_request_encrypted_file = Path(output_dir + '/' + parent_folder + '/' + self.encrypted_report_request_file)
        report_request_decrypted_file = Path(output_dir + '/' + parent_folder + '/' + self.decrypted_report_request_file)

        if report_request_encrypted_file.is_file():
            return True
        elif report_request_decrypted_file.is_file():
            return False
        elif report_request_file.is_file():
            return False

        return False
    
    def is_csv_file_encrypted(self, csv_file:str) -> bool:
        '''return true if csv file is encrypted'''
        
        if '_encrypted' in csv_file:
            return True
        else:
            return False