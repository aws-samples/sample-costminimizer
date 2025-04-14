# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from ..report_output_handler.report_output_folder_crawler import ReportOutputFolderCrawler
from ..report_output_handler.report_output_handler import ReportOutputMetaData
from ..security.cow_encryption import FileEncryptionOperationError
from ..utils.term_menu import launch_terminal_menu
from pathlib import Path
import sys


class DecryptEncryptOperationsCommand:

    '''This class is a wrapper around the encryption class. It is used to encrypt or decrypt a report folder.'''
    
    def __init__(self, appConfig, operation) -> None:
        self.appConfig = appConfig
        self.config = appConfig.config
        self.operation = operation

        self.rofc = ReportOutputFolderCrawler(self.appConfig)
        self.romd = ReportOutputMetaData(self.appConfig, [], [], '', False, False)
        self.report_directory = self.rofc.report_directory
        self.report_directory_for_ui = self.rofc.report_directory_for_ui
        self.tmp_folder = self.report_directory / self.config.internals['internals']['reports']['tmp_folder']
        self.selection_file = self.tmp_folder / self.config.internals['internals']['reports']['selection_file']

        if not self.tmp_folder.exists():
            self.tmp_folder.mkdir(exist_ok=True)

    def display_folder_menu(self) -> list:
        '''display a menu of report folders to select from'''

        report_folders = self.rofc.parse_report_folders_files() 
        report_folders.sort()  

        title = f'Select a report to decrypt: '
        subtitle = title
        menu_options_list = launch_terminal_menu(
            report_folders, 
            title=title, 
            subtitle=subtitle, 
            multi_select=False, 
            show_multi_select_hint=True, 
            show_search_hint=True)
        
        return menu_options_list[0]

    def encrypt_folder(self, folder_name:Path) -> None:
        '''encrypt a report folder'''
        self.appConfig.encryption.encrypt_directory(folder_name)
        self.appConfig.console.print(f'Encrypted contents of {folder_name}')

    def decrypt_folder(self, folder_name:Path) -> None:
        '''decrypt a report folder'''
        try:
            self.appConfig.encryption.decrypt_directory(folder_name)
        except FileEncryptionOperationError as e:
            log_file = self.appConfig.cow_config.get_internals_config()['internals']['logging']['log_file']
            self.appConfig.logger.info(f'Error decrypting report folder {folder_name}')
            self.appConfig.logger.exception(e)
            self.appConfig.console.print(f'[red]Error decrypting report folder {folder_name}. Your secret may have changed.  Please see {log_file} log for details.')
            sys.exit(1)
        except:
            raise
        self.appConfig.console.print(f'Decrypted contents of {folder_name}')

    def run(self) -> None:
        report_name = self.display_folder_menu()

        if self.operation == 'decrypt':
            self.decrypt_folder(Path(self.report_directory / report_name))
            data = {'decrypt': report_name}
            '''writing of a operation output tmp file'''
            self.romd.write_tmp_file(self.selection_file, data)
        elif self.operation == 'encrypt':
            self.encrypt_folder(Path(self.report_directory / report_name))
            data = {'encrypt': report_name}
            '''writing of a operation output tmp file'''
            self.romd.write_tmp_file(self.selection_file, data)
        else:
            if self.appConfig.mode == 'cli':
                self.appConfig.logger.info(f'Operation {self.operation} not supported.')
                print(f'Operation {self.operation} not supported.')
                sys.exit(0)

class EncryptOperationCommand(DecryptEncryptOperationsCommand):

    '''This class is a wrapper around the encryption class. It is used to encrypt a report folder.'''

    def __init__(self, app) -> None:
        operation = 'encrypt'
        super().__init__(app, operation)

class DecryptOperationCommand(DecryptEncryptOperationsCommand):

    '''This class is a wrapper around the encryption class. It is used to decrypt a report folder.'''

    def __init__(self, app) -> None:
        operation = 'decrypt'
        super().__init__(app, operation)

