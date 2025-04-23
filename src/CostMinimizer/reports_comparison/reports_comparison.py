# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "samuel LEPETRE"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import logging
import sys
from itertools import product
from ..commands.configure_tooling import ConfigureToolingCommand
from ..utils.yaml_loader import import_yaml_file
from ..report_output_handler.report_output_folder_crawler import ReportOutputFolderCrawler
import xlsxwriter, string, datetime, datetime
import pandas as pd
from pathlib import Path
from datetime import datetime
import pathlib
import tabulate as tabulate
from ..utils.term_menu import launch_terminal_menu
import click


v_COST_EIP_UNUSED = 3.72 #TODO this needs to be removed and come from a central source - perhaps DB?

class FeatureNotImplementedInModuleMode(Exception):
    pass

class ExceptionReadingCSVFileFormat(Exception):
    pass

class ExceptionCreatingXLSFile(Exception):
    pass

class ExceptionWritingResultsToXLSFile(Exception):
    pass

class ExceptionMergingAllDFToXLSFile(Exception):
    pass

class ExceptionComputeRegionsAccountsExcelFile(Exception):
    pass


#----------------------------------------------------------------------------------------------------------------------------------------------------
# CLASS CowReportComparisonBase
#   - init - logger, app and populate variables from central sources
#   - Base clase includes methods to obtain comparison metadata from report objects
#----------------------------------------------------------------------------------------------------------------------------------------------------
class CowReportComparisonBase():

    def __init__(self, appConfig, reports) -> None:
        self.logger = logging.getLogger(__name__)
        self.appConfig = appConfig
        self.config = appConfig.config
        self.report_crawler = ReportOutputFolderCrawler(self.appConfig)
        self.report_path = self.config.internals['internals']['reports']['reports_directory'] 
        self.report_request_file = self.config.internals['internals']['reports']['default_report_request']
        self.encrypted_report_request_file = self.config.internals['internals']['reports']['default_encrypted_report_request']
        self.decrypted_report_request_file = self.config.internals['internals']['reports']['default_decrypted_report_request']
        self.reports_module_path = self.config.internals['internals']['reports']['reports_module_path'] 
        self.available_reports = reports
        self.all_providers_completed_reports = []

        self.output_filename = self.config.internals['internals']['comparison']['filename']

        self.output_folder = self.report_crawler.set_output_folder_path()

        self.column_report_name = self.config.internals['internals']['comparison']['column_report_name']
        self.reports_directory = self.config.internals['internals']['comparison']['reports_directory']
        self.column_grouping = self.config.internals['internals']['comparison']['column_group_by']
        self.column_savings = self.config.internals['internals']['comparison']['column_savings']
        self.name_xls_main_sheet = self.config.internals['internals']['comparison']['name_xls_main_sheet']
        self.include_details_in_xls = self.config.internals['internals']['comparison']['include_details_in_xls']
        self.cost_pillar_columns_xls_list = [self.column_report_name, self.column_grouping, self.column_savings]

    def get_completed_reports_from_controller(self) -> list:
        return self.all_providers_completed_reports

#----------------------------------------------------------------------------------------------------------------------------------------------------
# CLASS CowReportComparison
#   - def run()
#   - def generate_xls_from_csv_files()
#   - def execute_comparison()
#----------------------------------------------------------------------------------------------------------------------------------------------------
class CowReportComparison(CowReportComparisonBase):
    '''
    controller for Comparison module
    
    parameters:
    app: main app
    '''
    def __init__(self, app, reports) -> None:
        super().__init__(app, reports)
        self.requested_reports = None
        self.worksheet_name = None #set by each report

        self.run()

    def _comparison_setup(self) -> None:
        pass
    
    def run(self):

        #run any setup instructions for the controller
        if self.appConfig.mode == 'cli':
            self._comparison_setup()
            self.execute_comparison()
        elif self.appConfig.mode == 'module':
            self._comparison_setup()
        #    raise FeatureNotImplementedInModuleMode(f'This featuer not implemented in module mode.')

    def create_reports_dir(self, output_folder) -> pathlib.Path:
        '''make reports directory inside of output directory'''
        reports_folder = output_folder / self.reports_directory
        reports_folder.mkdir(parents=True, exist_ok=True)

        return reports_folder

    def set_output_filename(self) -> str:
        '''generate absolute file path/name; return as string''' 

        reports_folder = self.create_reports_dir(Path(self.output_folder))
        v_FULL_DATETIME = datetime.today().strftime("%Y-%m-%d-%H-%M-%S") 
        return str(reports_folder) + "/COW_"+self.customer_name+"_"+v_FULL_DATETIME+"_"+self.output_filename

    def delete_repeated_elements(self, d):
        for key, value in list(d.items()):
            if (value[0] == 'missing') and len(set(value)) == 1:
                del d[key]
        return d

    def set_list_csv_mapping_per_report(self, lst_csv_files_found_per_report, report_csv_filename, selected_folders_for_comparison) -> dict:
        '''
        Ouput a dictionary which maps the report folder to the absolute csv filename
        i.e. {
            'ec2_low_util_instances_ta.csv': PosixPath('/tmp/ec2_low_util_instances_ta.csv'))
            }
        '''
    
        for csv_filename, report_foldername in product(report_csv_filename, selected_folders_for_comparison):
            parent_path = self.output_folder + "/" + str(report_foldername) + "/csv/"
            
            csv_filename_without_extension = csv_filename.replace(".csv", "")

            #need to check three states, 1) csv file exists, 2) csv file is encrypted, 3) csv file is decrypted
            if Path(parent_path + str(csv_filename)).is_file():
                # i.e. ebs_gp2_to_gp3.csv
                if not csv_filename in lst_csv_files_found_per_report:
                    lst_csv_files_found_per_report[csv_filename] = [Path(parent_path + str(csv_filename))]
                else:
                    lst_csv_files_found_per_report[csv_filename].append(Path(parent_path + str(csv_filename)))
            elif Path(parent_path + csv_filename_without_extension + '_encrypted.csv').is_file():
                # i.e. ebs_gp2_to_gp3_encrypted.csv
                if not csv_filename in lst_csv_files_found_per_report:
                    lst_csv_files_found_per_report[csv_filename] = [Path(parent_path + csv_filename_without_extension + '_encrypted.csv')]
                else:
                    lst_csv_files_found_per_report[csv_filename].append(Path(parent_path + csv_filename_without_extension + '_encrypted.csv'))
            elif Path(parent_path + csv_filename_without_extension + '_decrypted.csv').is_file():
                # i.e. ebs_gp2_to_gp3_decrypted.csv
                if not csv_filename in lst_csv_files_found_per_report:
                    lst_csv_files_found_per_report[csv_filename] = [Path(parent_path + csv_filename_without_extension + '_decrypted.csv')]
                else:
                    lst_csv_files_found_per_report[csv_filename].append(Path(parent_path + csv_filename_without_extension + '_decrypted.csv'))
            else:
                if not csv_filename in lst_csv_files_found_per_report:
                    lst_csv_files_found_per_report[csv_filename] = ["missing"]
                else:
                    lst_csv_files_found_per_report[csv_filename].append("missing")

        self.delete_repeated_elements(lst_csv_files_found_per_report) 
        
        return lst_csv_files_found_per_report
    
    def create_curated_csv_df(self, csv_file_df, title, csv_column_savings) -> pd.core.frame.DataFrame:
        '''curate csv data read in from .csv file'''
        try:
            csv_file_df[csv_column_savings] = csv_file_df[csv_column_savings].replace('[\$,]', '', regex=True).astype(float)
            csv_file_df[self.column_report_name] = title
        except:
            ExceptionReadingCSVFileFormat(f'Unable to convert type the dataframe CSV file based on COW definition {csv_column_savings}. Please contact the COW support team.')
            return []

        return csv_file_df

    def create_grouped_df(self, df, groupby_columns, sum_column, columns_list) -> pd.core.frame.DataFrame:
        '''Group the dataframe my provided columns; provided the column to sum values'''

        try:
            grouped_df = pd.DataFrame(df.groupby(groupby_columns).sum(sum_column))
            grouped_df = grouped_df.reset_index()
            grouped_df = grouped_df.rename(columns={groupby_columns[1]:columns_list[1], sum_column:columns_list[2] })
        except:
            ExceptionReadingCSVFileFormat(f'Unable to group by the CSV file based on COW definition column {sum_column}. Please contact the COW support team.')
            raise

        return grouped_df

    def test_only_empty_elements(self, d):
        l_found_elem_not_empty = 0
        for value in d:
            if (not value.empty):
                l_found_elem_not_empty += 1
        return l_found_elem_not_empty

    def merging_all_in_worksheet_df(self, df_ta_co_group, p_index_Domain_Type, p_columns_xls_list, p_value_savings, v_first_line_xls_list, p_selected_folders, p_csv_filenames) -> pd.core.frame.DataFrame:

        # Concat all filetypes for the first folder
        df_concat_all_filetypes = []
        l_IndexesOfSublistForAFiletype = list(range(0,len(p_selected_folders)*len(p_csv_filenames),len(p_selected_folders)))
        t_sublistForAFiletype = [df_ta_co_group[i] for i in l_IndexesOfSublistForAFiletype]

        if (self.test_only_empty_elements(t_sublistForAFiletype)>0):
            try:
                df_concat_all_filetypes = pd.pivot_table(pd.concat(t_sublistForAFiletype), index=p_index_Domain_Type, values=p_value_savings)
                df_concat_all_filetypes = df_concat_all_filetypes.reset_index()
                df_concat_all_filetypes.columns = p_columns_xls_list   
                self.logger.debug(tabulate.tabulate(df_concat_all_filetypes, headers='keys', tablefmt='psql', showindex="always"))
                df_ta_co_global = df_concat_all_filetypes
            except:
                ExceptionMergingAllDFToXLSFile('Exception merging all pandas dataframes!')
                print('Exception merging all pandas dataframes!')
                raise

            # if more than 1 folder (date) to compare
            if (len(p_selected_folders)>1):
                self.logger.info("Now merging " + str(len(p_selected_folders)) + " dataframes folders")
                
                for iFolderNumer in range(1, len(p_selected_folders)):
                    l_IndexesOfSublistForAFiletype = list(range(iFolderNumer,len(p_selected_folders)*len(p_csv_filenames),len(p_selected_folders)))
                    t_sublistForAFiletype = [df_ta_co_group[i] for i in l_IndexesOfSublistForAFiletype]
                    df_concat_all_filetypes = pd.pivot_table(pd.concat(t_sublistForAFiletype), index=p_index_Domain_Type, values=p_value_savings)
                    df_concat_all_filetypes = df_concat_all_filetypes.reset_index()
                    df_concat_all_filetypes.columns = p_columns_xls_list                
                    self.logger.debug(tabulate.tabulate(df_concat_all_filetypes, headers='keys', tablefmt='psql', showindex="always"))

                    # Concat all csv for the same type of file like ec2_low_util_instances_ta.csv
                    df_ta_co_global = pd.merge(df_ta_co_global, df_concat_all_filetypes, how="outer", on=p_index_Domain_Type)
                    self.logger.debug(tabulate.tabulate(df_concat_all_filetypes, headers='keys', tablefmt='psql', showindex="always"))
            
            # set columns values including one column for each folder
            df_ta_co_global.columns = v_first_line_xls_list 

            return df_ta_co_global
        return None

    def create_writer(self) -> xlsxwriter.workbook.Workbook:
        '''create and return writer'''
        try:
            writer = pd.ExcelWriter(self.set_output_filename(), engine='xlsxwriter')
        except:
            ExceptionCreatingXLSFile(f'Unable to create XLS file on local folder : {self.output_folder}')
            raise      

        return writer

    def set_workbook_formatting(self) -> dict:
        '''set workbook format options'''
        fmt = {
            'savings_format': {'num_format': '$#,##0'},
            'default_column_format': {'align': 'center', 'valign': 'center', 'text_wrap': True},
            'comparison_column_format': {'num_format': '$#,##0', 'bold': True, 'font_color': 'red','align': 'right', 'valign': 'right', 'text_wrap': True},
            'numeric_column_format': {'num_format': '000', 'bold': False, 'font_color': 'black','align': 'right', 'valign': 'right', 'text_wrap': True}
        }

        return fmt

    def create_worksheet_graph(self, df, worksheet, workbook, workbook_format, report_folder_regions_accounts):
        '''
        method writes a graph from the df provided

        ** This method will need rework, it needs to be further abstracted to allow for re-use with other comparison reports **
        '''
        (max_row, max_col) = df.shape
        worksheet.set_column('C:'+string.ascii_uppercase[max_col+2], 20, workbook.add_format(workbook_format['savings_format']))
        worksheet.set_column('A:A', 50, workbook.add_format(workbook_format['default_column_format']))
        worksheet.set_column('B:B', 30)

        chart = workbook.add_chart({'type': 'bar'})
        worksheet.insert_chart('G2', chart, {'x_scale': 2, 'y_scale': 2.5})

        comparison_column_format = workbook.add_format(workbook_format['comparison_column_format'])
        numeric_column_format = workbook.add_format(workbook_format['numeric_column_format'])

        worksheet.write('B'+str(max_row+3), 'TOTAL', comparison_column_format)

        worksheet.write('B'+str(max_row+5), 'Number of regions:', comparison_column_format)
        worksheet.write('B'+str(max_row+6), 'Number of accounts', comparison_column_format)

        for x in range(1,max_col+1):
            chart.set_title({'name': self.name_xls_main_sheet})
            showValue=True
            chart.add_series({
                'categories': '=\''+self.name_xls_main_sheet+'\'!$A$2:$B$'+str(round(max_row+1)),
                'values':     '=\''+self.name_xls_main_sheet+'\'!$'+string.ascii_uppercase[x+1]+'$2:$'+string.ascii_uppercase[x+1]+'$'+str(max_row+1),
                'name': '=\''+self.name_xls_main_sheet+'\'!$'+string.ascii_uppercase[x+1]+'$1',
                'data_labels': {'value': True}})
            worksheet.write_formula(
                string.ascii_uppercase[x+1]+str(max_row+3), 
                '=SUM('+string.ascii_uppercase[x+1]+'2:'+string.ascii_uppercase[x+1]+str(max_row+1) + ')', 
                comparison_column_format
                )

            self.logger.info('Adding CHART  : categories: ='+self.name_xls_main_sheet+'!$A$2:$B$'+str(round(max_row+1)))
            self.logger.info('              : values    : ='+self.name_xls_main_sheet+'\'!$'+string.ascii_uppercase[x+1]+'$2:$'+string.ascii_uppercase[x+1]+'$'+str(max_row+1))
            self.logger.info('              : name      : ='+self.name_xls_main_sheet+'\'!$'+string.ascii_uppercase[x+1]+'$1')        

        # if more than 2 columns then additional column for difference between the two 
        if (max_col>1):
            for y in range(2,max_row+2):
                worksheet.write_formula(string.ascii_uppercase[max_col+2]+str(y), '=(C'+str(y)+'-'+string.ascii_uppercase[max_col+1]+str(y) + ')', comparison_column_format)
        
        # TOTAL (sum of the column) for each folder (date of cow reports) at the bottom of the excel sheet
        worksheet.write_formula(string.ascii_uppercase[max_col+2]+str(max_row+3), '=SUM('+string.ascii_uppercase[max_col+2]+'2:'+string.ascii_uppercase[max_col+2]+str(max_row+1) + ')', comparison_column_format)
        worksheet.write(string.ascii_uppercase[max_col+2]+'1', 'COW', comparison_column_format)

        # Additional information for the number of regions and accounts at the bottom of the excel sheet
        item = 0
        worksheet.write_formula(string.ascii_uppercase[3]+str(max_row+5), 'Number of regions:', comparison_column_format)
        worksheet.write_formula(string.ascii_uppercase[3]+str(max_row+6), 'Number of accounts:', comparison_column_format)
        for report in report_folder_regions_accounts:
            try:
                worksheet.write_formula(string.ascii_uppercase[2+item]+str(max_row+5), str(len(report_folder_regions_accounts[item][1])), numeric_column_format)
                worksheet.write_formula(string.ascii_uppercase[2+item]+str(max_row+6), str(len(report_folder_regions_accounts[item][0])), numeric_column_format)
            except:
                ExceptionComputeRegionsAccountsExcelFile(f'Unable to compute the number of accounts and regions for folder  : {self.output_folder}')
                l_mess = f'Unable to compute the number of accounts and regions for folder  : {self.output_folder}'
                print(l_mess)
                self.logger.warning(l_mess)
            item = item + 1

    #----------------------------------------------------------------------------------------------------------------------------------------------
    # files *.csv generated by cow tool
    # CheckId,Account-Id,Account Display Name,TA Category,Status External,TA Check Name,Region,isSuppressed,---,Resources_Metadata
    #----------------------------------------------------------------------------------------------------------------------------------------------
    def generate_xls_from_csv_files(self, customer_name, selected_folders_for_comparison, reports_for_comparison={}, report_folder_regions_accounts=[]) -> str:
        '''
        generate comparison xlsx from csv files.
        when encrypted, we decrypt then reencrypt the file
        '''

        writer = self.create_writer()
        workbook = writer.book
        workbook_format = self.set_workbook_formatting() 
        
        df_ta_co_sheet = []
        df_ta_co_group = []
        df_ta_co_global = []
        report_csv_filename = []
        list_sheet_names_for_details = []
        comparison_metadata_from_report = {}
        l_lst_CSV_file_types_found = {}
        v_cost_pillar_first_line_xls_list = [self.column_report_name, self.column_grouping]

        self.logger.info("Number of folders to analyze : " + str(len(selected_folders_for_comparison)))
        
        if len(selected_folders_for_comparison) <= 0:
            l_mess = "List of CSV files folders for comparison is empty!"
            self.logger.info(l_mess)
            return l_mess
        
        for r in self.available_reports:
            report = r()

            is_requested_report = False
            for report_check in reports_for_comparison.keys():
                
                if report_check.split('.')[0] != report.name():
                    continue
                else:
                    is_requested_report = True
                    break
            
            if not is_requested_report:
                continue
            
            #only run reports which have comparison enabled
            if report.enable_comparison():
                report_csv_filename.append(f'{report.name()}.csv')
            else:
                continue

            self.worksheet_name = report.name()

            comparison_metadata_from_report[f'{report.name()}.csv'] = report.get_comparison_definition()
        
        self.logger.info(f'Found {len(report_csv_filename)} enabled reports in the cow tool configuration of reports.')

        #Create dictionary with folder as key and absolute path to file as value
        l_lst_CSV_file_types_found = self.set_list_csv_mapping_per_report(l_lst_CSV_file_types_found, report_csv_filename, selected_folders_for_comparison)
        if (len(l_lst_CSV_file_types_found)==0):
            l_mess = "List of CSV files folders compared with enabled reports is empty!"
            self.logger.info(l_mess)
            return l_mess
            
        df_ta_co_group.clear()
        l_IndexOfFileTypesIncrement = 0

        # ------------------------------------------------------------------------------------------------------------------------
        # BEGINNING OF LOOP ON FOLDERS & FILETYPES
        # For each different types of files like ec2_low_util_instances_ta.csv
        # ------------------------------------------------------------------------------------------------------------------------
        # loop filetypes

        for report_check, report_check_absolute_path in l_lst_CSV_file_types_found.items():
            for l_files_from_filetype_in_folders in report_check_absolute_path:
            
                self.logger.info('+' + '-'*98 + '+') 
                            
                if l_files_from_filetype_in_folders == 'missing':
                    df_empty = pd.DataFrame(data=None, columns=csv_definition_found['CSV_GROUP_BY'])
                    df_ta_co_group.append(df_empty)
                else:

                    l_aPath = l_files_from_filetype_in_folders.parent.parent.parts[-1]
                    
                    # Add specific column with folder (date) during each loop
                    if (l_aPath not in v_cost_pillar_first_line_xls_list):
                        v_cost_pillar_first_line_xls_list.append(l_aPath)

                    # Search definition of the csv file format based on the filename found like ec2_low_util_instances_ta.csv
                    csv_definition_found = comparison_metadata_from_report[report_check]
                
                    # If a definition is registered for the filename found like ec2_low_util_instances_ta.csv
                    if (len(csv_definition_found) > 0):

                        #read in csv file for report
                        usecols = [i+1 for i in range(len(csv_definition_found['CSV_COLUMNS']))]
                        names = csv_definition_found['CSV_COLUMNS']
                        
                        if self.report_crawler.is_csv_file_encrypted(str(l_files_from_filetype_in_folders)):
                            #decrypt file
                            self.appConfig.encryption.decrypt_file(l_files_from_filetype_in_folders, rename=True)
                            #rename to _decrypted
                            l_files_from_filetype_in_folders = Path(
                                str(l_files_from_filetype_in_folders.parent) + '/' + str(l_files_from_filetype_in_folders.stem).replace('_encrypted', '_decrypted') + '.csv')

                        csv_file_df = pd.DataFrame(pd.read_csv(str(l_files_from_filetype_in_folders), usecols=usecols , names=names, skiprows=1))

                        #re-encrypt file
                        self.appConfig.encryption.encrypt_file(l_files_from_filetype_in_folders, rename=True)

                    
                        #If csv file read in is empty, skip it
                        if csv_file_df.empty:
                            df_empty = pd.DataFrame(data=None, columns=csv_definition_found['CSV_COLUMNS_XLS'])
                            df_ta_co_group.append(df_empty)
                            l_mess = f'File {str(l_files_from_filetype_in_folders)} is empty => skipping the file.'
                            self.logger.warning(l_mess)
                            print(l_mess)
                            continue
                    
                        try:
                            csv_file_df = self.create_curated_csv_df(
                                csv_file_df, 
                                csv_definition_found['CSV_TITLE'],
                                csv_definition_found['CSV_COLUMN_SAVINGS']
                                )
                        except Exception as e:
                            df_empty = pd.DataFrame(data=None, columns=csv_definition_found['CSV_COLUMNS_XLS'])
                            df_ta_co_group.append(df_empty)
                            l_mess = f'Dataframe column type modification Exception occured {str(l_files_from_filetype_in_folders)}, skipping file.' +repr(e)
                            print(l_mess)
                            self.logger.info(l_mess)
                            continue
                        
                        df_ta_co_sheet.append(csv_file_df)
                        
                        list_sheet_names_for_details.append(csv_definition_found['CSV_ID'])
                            
                        try:
                            # group columns and sum estimated savings within the groupings
                            grouped_df = self.create_grouped_df(
                                csv_file_df, 
                                groupby_columns=csv_definition_found['CSV_GROUP_BY'], 
                                sum_column=csv_definition_found['CSV_COLUMN_SAVINGS'], 
                                columns_list=csv_definition_found['CSV_COLUMNS_XLS']
                                )
                        except Exception as e:
                            df_empty = pd.DataFrame(data=None, columns=csv_definition_found['CSV_COLUMNS_XLS'])
                            df_ta_co_group.append(df_empty)
                            l_mess = f'Configuration issue. Dataframe Group By Exception occured with {str(l_files_from_filetype_in_folders)} / ' + repr(e) + ' => skipping file.'
                            print(l_mess)
                            self.logger.warning(l_mess)
                            continue

                        df_ta_co_group.append(grouped_df)
                        
                        l_IndexOfFileTypesIncrement += 1

                        self.logger.debug(tabulate.tabulate(df_ta_co_group[l_IndexOfFileTypesIncrement-1], headers='keys', tablefmt='psql', showindex="always"))

        # ------------------------------------------------------------------------------------------------------------------------
        # END OF LOOP ON FOLDERS & FILETYPES
        # ------------------------------------------------------------------------------------------------------------------------

        # ------------------------------------ MERGING DIFFERENT FOLDERS FOUND & FILETYPES
        try:
            df_ta_co_global = self.merging_all_in_worksheet_df(df_ta_co_group, [self.column_report_name, self.column_grouping], 
                                                           self.cost_pillar_columns_xls_list, self.column_savings, 
                                                           v_cost_pillar_first_line_xls_list,
                                                           selected_folders_for_comparison, l_lst_CSV_file_types_found)

            if (df_ta_co_global is None):
                l_mess = f'''
                Unable to merge : all dataframes are empty. Nb of dataframes = {len(df_ta_co_group)}.
                There may be an issue with one of the files.'''
                return l_mess
            

            self.logger.debug(tabulate.tabulate(df_ta_co_global, headers='keys', tablefmt='psql', showindex="always"))
            #print(tabulate.tabulate(df_ta_co_global, headers='keys', tablefmt='psql', showindex="always"))
            
            # create new worksheet as pivot table and push it to excel
            df_ta_co_global = pd.pivot_table(df_ta_co_global, index=[self.column_report_name, self.column_grouping])

            try:
                df_ta_co_global.to_excel(writer, sheet_name=self.name_xls_main_sheet)
            except:
                l_mess = f'Unable to create XLS file on local folder : {self.output_folder}'
                ExceptionWritingResultsToXLSFile(l_mess)  
                return l_mess   

            # ------------------------------------ DETAILS WORKSHEETS
            if (len(df_ta_co_sheet)>=1) and ((self.include_details_in_xls) in map(''.join, product(*zip('yes','YES')))):
                self.logger.info("Writing details for worksheets range(" + str(len(list_sheet_names_for_details)) + ")")
                for i in range(len(list_sheet_names_for_details)):
                    # create new worksheet with details of the specific csv results like ec2_low_util_instances_ta.csv
                    df_ta_co_sheet[i].to_excel(writer, sheet_name=list_sheet_names_for_details[i+1])
                    self.logger.info("Writing details for worksheet(" + str(i+3) + ') : ' + list_sheet_names_for_details[i+1] + " / Nbr lines = " + str(len(df_ta_co_sheet[i])))

            # Creating COST OPTIM Graph ----------------------------------------------------------------------------------------------
            self.logger.info("Creating COST OPTIM Graph in XLSX file !")
            worksheet = writer.sheets[self.name_xls_main_sheet]

            self.create_worksheet_graph(df_ta_co_global, worksheet, workbook, workbook_format, report_folder_regions_accounts)

            mess = f'{self.set_output_filename()}'
            print('SUCCESS: Excel comparison report has been written to: '+mess)
            writer.close()
            return mess

        except:
            l_mess = f'''
                    Unable to merge : all dataframes are empty. Nb of dataframes = {len(df_ta_co_group)}.
                    There may be an issue with one of the files.'''
            if self.appConfig.mode == 'cli':
                ExceptionMergingAllDFToXLSFile(l_mess)
                return l_mess
            else:
                self.appConfig.alerts['comparison'] = l_mess
        
        return

    def get_customer_selection(self) -> str:
        '''return the customer name selected'''
        customer_configuration = ConfigureToolingCommand(self.appConfig).list_configured_customers(list_only=False)
        
        return customer_configuration[0]   

    def display_menu_for_reports(self, title:str, customer_report_folders:list, multi_select=True, show_multi_select_hint=True, show_search_hint=True):
        '''display menu for reports'''
        subtitle = title
        menu_options_list = launch_terminal_menu(
            customer_report_folders, 
            title=title, 
            subtitle=subtitle, 
            multi_select=multi_select, 
            show_multi_select_hint=show_multi_select_hint, 
            show_search_hint=show_search_hint)
        
        return menu_options_list

    def parse_report_request_file_of_selected_report(self, customer_report_folder) -> list:
        '''parse report request file and return a list of hashed accounts, regions and a dict of reports'''
        parent_path = Path(self.output_folder + '/' + customer_report_folder)
        
        #if report_request file is encrypted, decrypt it
        if self.report_crawler.is_report_request_encrypted(customer_report_folder):
            self.appConfig.encryption.decrypt_file(parent_path / self.encrypted_report_request_file, rename=True)
        
        rr = ''

        #import decrypted file if it exists i.e. report_request_decrypted.yaml
        decrypted_report_request_file = parent_path / self.decrypted_report_request_file
        if decrypted_report_request_file.is_file():
            rr = import_yaml_file(str(decrypted_report_request_file))
            report_request_file = decrypted_report_request_file

        #import default file if decrypted file does not exist (default file is assumed to be clear text) i.e. report_request.yaml
        default_report_request_file = parent_path / self.report_request_file
        if default_report_request_file.is_file():
            rr = import_yaml_file(str(default_report_request_file))
            report_request_file = default_report_request_file
       
        #if we successfully imported a report request file, hash accounts, regions and pull reports
        if isinstance(rr, dict):
            hashed_accounts = self.appConfig.encryption.hash_list_md5(rr['customers'][self.customer_name]['accounts'])
            hashed_regions = self.appConfig.encryption.hash_list_md5(rr['customers'][self.customer_name]['regions'])
            reports = rr['reports']

            #reencrypt repqort request file
            self.appConfig.encryption.encrypt_file(report_request_file, rename=True)
        else:
            #if report_request file was not found
            hashed_accounts = []
            hashed_regions = []
            reports = []
        
        return [hashed_accounts, hashed_regions, reports]
    
    def get_regions_accounts_report_request_file_of_selected_report(self, customer_report_folder) -> list:
        '''parse report request file and return a list of hashed accounts, regions and a dict of reports'''
        parent_path = Path(self.output_folder + '/' + customer_report_folder)
        
        #if report_request file is encrypted, decrypt it
        if self.report_crawler.is_report_request_encrypted(customer_report_folder):
            self.appConfig.encryption.decrypt_file(parent_path / self.encrypted_report_request_file, rename=True)
        
        rr = ''

        #import decrypted file if it exists i.e. report_request_decrypted.yaml
        decrypted_report_request_file = parent_path / self.decrypted_report_request_file
        if decrypted_report_request_file.is_file():
            rr = import_yaml_file(str(decrypted_report_request_file))
            report_request_file = decrypted_report_request_file

        #import default file if decrypted file does not exist (default file is assumed to be clear text) i.e. report_request.yaml
        default_report_request_file = parent_path / self.report_request_file
        if default_report_request_file.is_file():
            rr = import_yaml_file(str(default_report_request_file))
            report_request_file = default_report_request_file
       
        #if we successfully imported a report request file, hash accounts, regions and pull reports
        if isinstance(rr, dict):
            nb_accounts = rr['customers'][self.customer_name]['accounts']
            nb_regions = rr['customers'][self.customer_name]['regions']

            #reencrypt repqort request file
            self.appConfig.encryption.encrypt_file(report_request_file, rename=True)
        else:
            #if report_request file was not found
            nb_accounts = []
            nb_regions = []
            reports = []
        
        return [nb_accounts, nb_regions]

    #----------------------------------------------------------------------------------------------------------------------------------------------
    def execute_comparison(self):
        customer_report_folders = []
        
        #display customer menu 
        self.customer_name = self.get_customer_selection()

        #a list of report folders for the selected customer
        customer_report_folders = ReportOutputFolderCrawler(self.appConfig).parse_report_folders_files(self.customer_name) 
        #TODO this sorting needs help as days starting with 1 or 2 will not sort correctly - it should probably be sorted at origin
        customer_report_folders.sort()    
            
        #t least 2 reports are needed for comparison
        if len(customer_report_folders)<2:
            msg=f"Customer {self.customer_name} does not have two or more report folders in {Path(self.output_folder).resolve()}"
            self.logger.info(msg)
            print(msg)

        #initial menu of reports to select from
        menu_options_list = self.display_menu_for_reports(f'Select a report to compare for {self.customer_name}: ', 
                                                          customer_report_folders, 
                                                          multi_select=False, 
                                                          show_multi_select_hint=True, 
                                                          show_search_hint=True)
        
        initial_selected_report = menu_options_list[0]
        
        #generate a signature for the selected report - this will be used to pull a list of comparable reports
        selected_report_signature = self.parse_report_request_file_of_selected_report(initial_selected_report)

        '''
        Obtain a list of matching reports.  Matching reports will need to have the same accounts and regions as the selected report.
        They will also need to have at least one of the report_checks in the selected report.
        '''
        l_strict_comparison_only = click.prompt("Do you want ([Y]es or [N]o) to select reports that EXCLUSIVELY contains the same accounts & regions ? ", confirmation_prompt=False, hide_input=False, default = 'Y')
        
        matching_report_folders = []

        for report_folder in customer_report_folders:
            if report_folder == initial_selected_report:
                continue

            report_signature = self.parse_report_request_file_of_selected_report(report_folder)
            
            #check if accounts are matching and regions are matching

            if l_strict_comparison_only == 'Y':
                if selected_report_signature[0] == report_signature[0] and selected_report_signature[1] == report_signature[1]:
                    for report_check in report_signature[2].keys():
                        if report_check in selected_report_signature[2].keys():
                            matching_report_folders.append(report_folder)
                            break
            else:
                matching_report_folders.append(report_folder)
        
        if matching_report_folders == []:
            msg = f'''
            No matching reports found for {self.customer_name} report: {initial_selected_report}.
            Reports need to have identical accounts and regions.
            '''
            if self.appConfig.mode == 'cli':
                self.logger.info(msg)
                print(msg)
                sys.exit(0)
            else:
                self.logger.info(msg)
                self.appConfig.alerts['comparison'] = msg
        
        #second menu - select the reports to compare to the initial selected report
        menu_options_list = self.display_menu_for_reports(f'Matching reports for customer: {self.customer_name} report: {initial_selected_report}', 
                                                          matching_report_folders, multi_select=True, 
                                                          show_multi_select_hint=True, 
                                                          show_search_hint=True)

        #generate a list of report names to be used for the comparison
        list_options = [i[0] for i in menu_options_list]

        #add the initial selected report to the list of reports to be compared
        list_options.insert(0, initial_selected_report)
           
        report_folder_regions_accounts = []
        for report_folder in list_options:
            report_folder_regions_accounts.append(self.get_regions_accounts_report_request_file_of_selected_report(report_folder))

        #generate the comparison report
        l_mess = self.generate_xls_from_csv_files(self.customer_name, list_options, reports_for_comparison=selected_report_signature[2], report_folder_regions_accounts=report_folder_regions_accounts)
        if (l_mess is not None) and (len(str(l_mess))>0):
            print(l_mess)
            self.logger.info(l_mess)