# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import os, sys
import logging
import json
import smtplib
from pathlib import Path
import pathlib
import shutil
import yaml
import pandas as pd
import xlsxwriter
#For email
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate


class ReportDirectoryStructureCreationErrorException(Exception):
    pass

class ExceptionCreatingXLSFile(Exception):
    pass

class ReportOutputHandlerBase:

    def __init__(self, appConfig, completed_reports, completion_time, determine_report_directory=True, create_directory_structure=False) -> None:
        self.logger = logging.getLogger(__name__)
        self.appConfig = appConfig
        self.config = appConfig.config

        self.files_to_encrypt = []
        self.folders_to_encrypt = []
        self.file_extensions_to_encrypt = ['.csv', '.yaml', '.sql', '.json']

        report_file_name = self.appConfig.internals['internals']['reports']['report_output_name']
        self.completion_time = self.appConfig.auth_manager.appInstance.start #moving away from completion time and using time provided by app
        self.report_time = self.appConfig.auth_manager.appInstance.report_time
        self.completed_reports = completed_reports
        self.create_directory_structure = create_directory_structure
        if determine_report_directory or self.appConfig.auth_manager.appInstance.mode == 'module':
            self.output_folder = self.get_output_folder()

        self.report_directory = self.get_report_directory() #i.e $ACCOUNT_NUMBER/$ACCOUNT_NUMBER-2023-12-12-12-12

        self.tmp_folder = self.report_directory / self.appConfig.internals['internals']['reports']['tmp_folder']

        self.async_run_filename = self.appConfig.internals['internals']['reports']['async_run_filename']
        self.async_report_filename = self.appConfig.internals['internals']['reports']['async_report_complete_filename']


        self.report_metadata = None
        self.csv_directory = None
        self.pptx_directory = None
        
        self.name_of_main_worksheet = 'Estimated savings'

    def make_report_directory_structure(self) -> None:
        # create report output directory structure
        self.report_metadata = self.report_directory / 'metadata'
        self.csv_directory = self.report_directory / 'xls'
        self.pptx_directory = self.report_directory / 'powerpoint_report'

        self.folders_to_encrypt = [self.report_metadata, self.csv_directory, self.pptx_directory]

        try:
            os.makedirs(self.report_directory, exist_ok=True)
        except Exception as exc:
            self.logger.error('Unable to create report output directory %s', self.report_directory)
            raise ReportDirectoryStructureCreationErrorException(f'Unable to create report output directory {self.report_directory}')from exc

        try:
            os.makedirs(self.tmp_folder, exist_ok=True)
        except Exception as exc:
            self.logger.error('Unable to create report output directory %s', self.tmp_folder)
            raise ReportDirectoryStructureCreationErrorException(f'Unable to create report output directory {self.tmp_folder}')from exc

        try:
            os.makedirs(self.report_metadata, exist_ok=True)
        except Exception as exc:
            self.logger.error('Unable to create report metadata directory %s', self.report_metadata)
            raise ReportDirectoryStructureCreationErrorException(f'Unable to create report metadata directory {self.report_metadata}')from exc

        try:
            os.makedirs(self.csv_directory, exist_ok=True)
        except Exception as exc:
            self.logger.error('Unable to create report output directory %s', self.csv_directory)
            raise ReportDirectoryStructureCreationErrorException(f'Unable to create report output directory {self.csv_directory}') from exc

        try:
            os.makedirs(self.pptx_directory, exist_ok=True)
        except Exception as exc:
            self.logger.error('Unable to create report output directory %s', self.pptx_directory)
            raise ReportDirectoryStructureCreationErrorException(f'Unable to create report output directory {self.pptx_directory}') from exc

    def get_output_folder(self) -> pathlib.PosixPath:
        #if running inside a container
        if self.appConfig.installation_type in ('container_install'):
            output_folder = Path(self.appConfig.config['container_mode_home']) #/root/.cow
        else:
            output_folder = Path(self.appConfig.config['output_folder']) #$HOME/cow

        return output_folder

    def get_report_directory(self) -> pathlib.PosixPath:
        # get top level report directory
        #report_directory = '.'
        
        cur_table = self.appConfig.cur_table_arguments_parsed if self.appConfig.cur_table_arguments_parsed else self.appConfig.config['cur_table']
        report_directory = cur_table + '-' + self.report_time

        return self.output_folder / self.appConfig.config['aws_cow_account'] / report_directory

    def delete_report(self, customer, report_time) -> bool:
        report_name = f'{customer}-{report_time}'
        print(f'Deleting report: {self.get_output_folder() / report_name}')
        shutil.rmtree(self.get_output_folder() / report_name)

        self.appConfig.database.delete_report(customer, report_time)
        return True

class ReportOutputHandler(ReportOutputHandlerBase):
    # exists only to invoke base and obtain report_directory information
    def __init__(self, app, completed_reports, completion_time) -> None:
        super().__init__(app, completed_reports, completion_time)

class ReportOutputMetaData(ReportOutputHandlerBase):

    def __init__(self, app, completed_reports, failed_reports, completion_time, determine_report_directory=True, create_directory_structure=False) -> None:
        super().__init__(app, completed_reports, completion_time, determine_report_directory, create_directory_structure)

        if determine_report_directory and create_directory_structure:
            self.make_report_directory_structure() #create directory structure

        self.failed_reports = failed_reports

        # self.write_to_csv()
        self.write_to_yaml()
        # self.write_failed_logs()
        # self.write_execution_ids_to_log()

    def write_tmp_file(self, filename, data):
        # write data to tmp file in json format
        f = open(filename.resolve(), "w", encoding='utf-8')
        f.write(json.dumps(data))
        f.close()

    def write_to_csv(self):

        report_directory = self.report_directory + '/' + 'csv'

        try:
            os.makedirs(report_directory, exist_ok=True)
        except ExceptionCreatingXLSFile as exc:
            self.logger.error('Unable to create report output directory %s', report_directory)
            raise ReportDirectoryStructureCreationErrorException(f'Unable to create report output directory {report_directory}') from exc

        for report in self.completed_reports:

            if report.get_fetchability() is True:
                report.report_output_phase = True
                raw_output_filename = report_directory / report.name()
                output_filename = raw_output_filename.with_suffix('.csv')

                report.get_report()['data'].to_csv(f'{output_filename.resolve()}')

                self.appConfig.encryption.encrypt_file(output_filename.resolve(), rename=True)

    def write_to_yaml(self) -> None:
        # write report_request to YAML
        yaml_filename = self.report_directory / self.appConfig.internals['internals']['reports']['default_decrypted_report_request']

        aws_cow_account = self.appConfig.config['aws_cow_account']
        
        if hasattr(self.appConfig, 'using_tags') and self.appConfig.using_tags is True: 
            user_tags = self.appConfig.user_tag_values
        else:
            user_tags = None   
        if not hasattr(self.appConfig, 'tag'):
            self.appConfig.tag = 'no_tag_provided'

        customer_yaml_file = {
            'tag': self.appConfig.tag,
            'aws_cow_account': aws_cow_account,
            'reports': self.appConfig.reports.get_all_reports(),
            'user_tags' : json.dumps(user_tags)
        }

        '''
        #TODO not all values are written consistently into the YAML
        file. YAML does a good job of loading it correctly.  But for 
        readability sakes, we should sanitize the data being dumped.
        '''

        with open(yaml_filename, 'w+', encoding='utf-8') as f:
            yaml.dump(customer_yaml_file, f)

        self.logger.info('Report YAML Request written to: %s', yaml_filename)

    def write_failed_logs(self) -> None:

        report_directory = self.report_directory / 'logs'

        try:
            os.makedirs(report_directory, exist_ok=True)
        except Exception as exc:
            self.logger.error('Unable to create report output directory %s', report_directory)
            raise ReportDirectoryStructureCreationErrorException(f'Unable to create report output directory {report_directory}') from exc

        reports = self.completed_reports + self.failed_reports

        for report in reports:
            if isinstance(report.failed_report_logs, dict):
                if report.name() in report.failed_report_logs.keys():

                    report_log_filename = report_directory / f'{report.name()}_failed_request.json'

                    for event in report.failed_report_logs[report.name()]:

                        with open(str(report_log_filename), 'a', encoding='utf-8') as fail_log:
                            fail_log.write(json.dumps(event))

    def write_execution_ids_to_log(self) -> None:

        report_directory = self.report_directory / 'logs'

        try:
            os.makedirs(report_directory, exist_ok=True)
        except Exception as exc:
            self.logger.error('Unable to create report output directory %s', report_directory)
            raise ReportDirectoryStructureCreationErrorException(f'Unable to create report output directory {report_directory}') from exc

        report_log_filename = report_directory / 'execution_ids.json'

        reports = self.completed_reports + self.failed_reports

        execution_ids = []
        for report in reports:
            execution_ids.append(report.execution_ids)

        with open(str(report_log_filename), 'w', encoding='utf-8') as exec_log:
            exec_log.write(json.dumps(execution_ids))

class ReportOutputExcel(ReportOutputHandlerBase):

    def __init__(self, app, completed_reports, completion_time) -> None:
        super().__init__(app, completed_reports, completion_time)

        self.make_report_directory_structure() #create directory structure

        self.raw_output_filename = self.report_directory / self.appConfig.report_file_name
        self.output_filename = self.raw_output_filename.with_suffix('.xlsx')

    def write_to_excel(self) -> None:
        # write report into report output as sheets
        self.create_excel_summary_sheet(self.csv_directory, self.output_filename) #create dummy summary for now #TODO

        msg=f'\n[white]Excel Report Output saved into: [yellow]{self.output_filename}'
        self.appConfig.console.print(msg)
        self.logger.info(msg)

        if self.appConfig.arguments_parsed.send_mail:
            self.send_excel_report(self.appConfig.arguments_parsed.send_mail, self.appConfig.config['ses_login'], self.appConfig.config['ses_password'], self.appConfig.config['ses_region'])

    def send_excel_report(self, email_address, login, password, region):
        try:
            msg = MIMEMultipart()
            msg['From'] = self.appConfig.config['ses_from']  # Replace with email passed in parameter or config db
            msg['To'] = email_address
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = f'Cost Optimization Tooling - {__tooling_name__} XLS Report'

            msg.attach(MIMEText(f'Please find attached the Cost Optimization Tooling - XLS report. \n Regards \n {__tooling_name__} Automation Tooling'))

            with open(self.output_filename, 'rb') as file:
                part = MIMEApplication(file.read(), Name=self.appConfig.report_file_name)
            part['Content-Disposition'] = f'attachment; filename="{self.appConfig.report_file_name}"'
            msg.attach(part)

            smtp = smtplib.SMTP(self.appConfig.config['ses_smtp'], 587)  # Replace with your SMTP server details

            # Enable debug output (remove in production)
            #smtp.set_debuglevel(1)
            
            # Identify ourselves to SMTP server
            smtp.ehlo()
            
            # Start TLS encryption
            if smtp.has_extn('STARTTLS'):
                smtp.starttls()
                smtp.ehlo()  # Second EHLO after TLS

            smtp.login(login, password)  # Replace with your email and password
            smtp.sendmail(msg['From'], msg['To'], msg.as_string())
            smtp.close()

            self.logger.info('Report sent successfully to: %s', email_address)
            self.appConfig.console.print(f'\n[blink][yellow]Report sent successfully to: {email_address}')

        except smtplib.SMTPConnectError:
            self.appConfig.console.print(f"\n[red]ERROR : Failed to connect to SMTP server")
            return False
        except smtplib.SMTPServerDisconnected:
            self.appConfig.console.print("\n[red]ERROR : Server disconnected unexpectedly")
            return False
        except smtplib.SMTPException as e:
            self.appConfig.console.print(f"\n[red]ERROR : SMTP error occurred => {str(e)}")
            return False
        except Exception as e:
            self.appConfig.console.print(f"\n[red]ERROR : An error occurred => {str(e)}")
            return False
        finally:
            try:
                smtp.quit()
            except Exception as e:
                logging.exception("Error occurred while closing SMTP connection", e, stack_info=True, exc_info=True)  # import logging

    def create_writer(self, output_filename) -> xlsxwriter.workbook.Workbook:
        # create and return writer
        writer = pd.ExcelWriter(output_filename, engine='xlsxwriter')

        return writer

    def set_workbook_formatting(self) -> dict:
        # set workbook format options
        fmt = {
            'savings_format': {'num_format': '$#,##0'},
            'default_column_format': {'align': 'left', 'valign': 'bottom', 'text_wrap': True},
            'large_description_format': {'align': 'left', 'valign': 'bottom', 'text_wrap': True},
            'comparison_column_format': {'num_format': '$#,##0', 'bold': True, 'font_color': 'red','align': 'right', 'valign': 'right', 'text_wrap': True}
        }
        return fmt

    def format_worksheet(self, df, workbook, worksheet, workbook_format, name_xls_main_sheet):
        # method writes a graph from the df provided

        # ** This method will need rework, it needs to be further abstracted to allow for re-use with other comparison reports **
        (max_row, _) = df.shape
        worksheet.set_column('A:A', 35, workbook.add_format(workbook_format['default_column_format'])) #index
        worksheet.set_column('B:B', 35, workbook.add_format(workbook_format['default_column_format'])) #common name
        worksheet.set_column('C:C', 90, workbook.add_format(workbook_format['large_description_format'])) #description
        worksheet.set_column('D:D', 10, workbook.add_format(workbook_format['default_column_format'])) #service
        worksheet.set_column('E:E', 20, workbook.add_format(workbook_format['default_column_format'])) #domain
        worksheet.set_column('F:F', 20, workbook.add_format(workbook_format['savings_format'])) #savings
        worksheet.set_column('G:G', 90, workbook.add_format(workbook_format['large_description_format'])) #recommendation

        comparison_column_format = workbook.add_format(workbook_format['comparison_column_format'])

        #write total
        worksheet.write('B'+str(max_row+3), 'TOTAL', comparison_column_format)

        #write sum formula for savings
        worksheet.write_formula(
            'F'+str(max_row+3),
            '=SUM(F2:F' + str(max_row+1) + ')',
            comparison_column_format
            )

    def add_domain_savings_chart(self, df, workbook, target_worksheet, datasource_sheet_name, title, target_cell):
        (max_row, _) = df.shape
        chart = workbook.add_chart({'type': 'pie'})
        target_worksheet.insert_chart(target_cell, chart, {'x_scale': 1, 'y_scale': 1})

        chart.set_title({'name': title})
        categories = '=\''+str(datasource_sheet_name)+'\'!$A$2:$A$'+str(round(max_row+1))
        values = '=\''+str(datasource_sheet_name)+'\'!$B$2:$B$'+str(max_row+1)
        name = '=\''+str(datasource_sheet_name)+'\'!$A$1'
        data_lables = {'value': True}

        chart.add_series({
            'categories': categories,
            'values': values,
            'name': name,
            'data_labels': data_lables})

    def add_savings_by_check_chart(self, df, workbook, worksheet, name_xls_main_sheet):
        (max_row, _) = df.shape
        chart = workbook.add_chart({'type': 'bar'})
        worksheet.insert_chart('A1', chart, {'x_scale': 2.5, 'y_scale': 3})

        chart.set_title({'name': str(name_xls_main_sheet)})
        categories = '=\''+str(name_xls_main_sheet)+'\'!$B$2:$B$'+str(round(max_row+1))
        values = '=\''+str(name_xls_main_sheet)+'\'!$F$2:$F$'+str(max_row+1)
        name = '=\''+str(name_xls_main_sheet)+'\'!$F$1'
        data_lables = {'value': True}

        chart.add_series({
            'categories': categories,
            'values': values,
            'name': name,
            'data_labels': data_lables})

    def insert_df_into_excel_summary_sheet(self, df, writer, sheetname, index=True):
        # insert dataframe values into summary sheet for estimated savings
        # Assuming your DataFrame is named 'df'

        try:
            df.to_excel(writer, sheet_name=str(sheetname), float_format='%.2f', index=index)
        except Exception as exc:
            raise ExceptionCreatingXLSFile(f'Unable to save df datas into XLS file on local folder : {self.output_folder}') from exc

    def create_readme_sheet(self) -> pd.DataFrame:
        # create readme sheet for report output
        data = {'README': ['''This report is created by the CostMinimizer Tool.  It is a summary of the estimated savings for the checks that were processed.
The report is broken down by service and domain.  To view granular account level and resource level information please refer to the xls
files located in the accompanying xls/ folder.

You can develop your own check or customize any existing check.
A good way to do this is to use a GenAI coding tool and ask it to duplicate an existing check but modify it for a specific potential saving. 

If there are any failures in your CostMinimizer Tool run, they should log information in your cow_log.log file.  For more information on
troubleshooting please see our FAQ at: https://github.com/aws-samples/sample-costminimizer''']}

        df = pd.DataFrame(data=data)

        return df

    def deliver_xlsx_file_via_email(self):
        #Time to deliver the file to S3
        if self.appConfig.config['aws_cow_s3_bucket']:
            try:
                try:
                    s3= self.appConfig.auth_manager.aws_cow_account_boto_session.client('s3')
                except Exception as e:
                    self.appConfig.console.print('\n[red]Unable to establish boto session for s3. \nPlease verify credentials in ~/.aws/ or Environment Variables like account ID, region and role ![/red]')
                    sys.exit()

                s3.upload_file( self.appConfig.report_file_name, self.appConfig.config['aws_cow_s3_bucket'], self.appConfig.report_file_name)
                self.logger.info(f"Successfuly uploaded file {self.appConfig.report_file_name} into bucket {self.appConfig.config['aws_cow_s3_bucket']}")
            except:
                self.logger.warning(f"[red]Error while trying to upload XLSX file into bucket {self.appConfig.config['aws_cow_s3_bucket']}")

        if self.appConfig.config['ses_send']:
            try:
                #Email logic
                msg = MIMEMultipart()
                msg['From'] = self.appConfig.config['ses_from']
                msg['To'] = COMMASPACE.join(self.appConfig.config['ses_send'].split(","))
                msg['Date'] = formatdate(localtime=True)
                msg['Subject'] = f"{__tooling_name__} Report"
                text = f"Find your {__tooling_name__} report attached\n\n"
                msg.attach(MIMEText(text))
                with open( self.appConfig.report_file_name, "rb") as fil:
                    part = MIMEApplication(
                        fil.read(),
                        Name=self.appConfig.report_file_name
                    )
                part['Content-Disposition'] = 'attachment; filename="%s"' % self.appConfig.report_file_name
                msg.attach(part)
                #SES Sending
                try:
                    ses= self.appConfig.auth_manager.aws_cow_account_boto_session.client('ses')
                except Exception as e:
                    self.appConfig.console.print('\n[red]Unable to establish boto session for Ses. \nPlease verify credentials in ~/.aws/ or Environment Variables like account ID, region and role ![/red]')
                    sys.exit()

                result = ses.send_raw_email(
                    Source=msg['From'],
                    Destinations=self.appConfig.config['ses_send'].split(","),
                    RawMessage={'Data': msg.as_string()}
                )     
                self.logger.info(f"Successfuly sent XLSX file via email to {self.appConfig.config['ses_send']}")
            except:
                self.logger.warning(f"Error while trying to send XLSX file via email to {self.appConfig.config['ses_send']}")


    def create_excel_summary_sheet(self, output_folder, output_filename) -> None:
        # create report summary sheet for estimated savings

        summary_rows = []
        index_row = []

        #group savings by domain
        try:
            writer_summary= self.create_writer(output_filename)

            workbook = writer_summary.book
            workbook_format = self.set_workbook_formatting()

            #readme sheet
            readme_worksheet_name = 'README'
            readme_worksheet = workbook.add_worksheet(readme_worksheet_name)

            #summary sheet
            summary_sheet_name = 'Summary'
            summary_worksheet = workbook.add_worksheet(summary_sheet_name)
            ssdf = pd.DataFrame({'Summary': ['Summary']})

            #estimated savings
            worksheet = workbook.add_worksheet(self.name_of_main_worksheet)

            #savings by domain
            domain_sheet_name = 'Savings By Domain'
            domain_worksheet = workbook.add_worksheet(domain_sheet_name)

            #savings by domain
            service_sheet_name = 'Savings By Service'
            service_worksheet = workbook.add_worksheet(service_sheet_name)

            for report in self.completed_reports:

                if report.report_type() == 'processed':
                    try:
                        common_name = report.common_name()[:30]
                    except Exception:
                        common_name = 'N/A'

                    try:
                        domain_name = report.domain_name()
                    except Exception:
                        domain_name = 'N/A'

                    if report.service_name() in ['Cost Explorer']:
                        report.generateExcel(writer_summary)
                    else:
                        index_row.append(report.name())
                        l_savings = report.calculate_savings()
                        row = [
                            common_name,
                            report.description(),
                            report.service_name(),
                            domain_name,
                            l_savings,
                            report.recommendation
                            ]                        
                        summary_rows.append(row)

                        report.generateExcel(writer_summary)

                    self.appConfig.console.print(f"[green]Adding new worksheet in XLS file: [yellow]{report.service_name()} - {report.name()}")

                    try:
                        writer= self.create_writer( (output_folder  / report.name()).with_suffix('.xlsx'))
                        report.generateExcel(writer)
                        writer.close()
                    except Exception as exc:
                        raise ExceptionCreatingXLSFile(f'Unable to create XLS report tab in Excel file: {exc}') from exc

            df = pd.DataFrame(summary_rows,
                index=index_row,
                columns=['Common Name', 'Description', 'Service', 'Domain', 'Estimated Savings', 'Recommendation'])
            dgbdf = df.groupby('Domain')['Estimated Savings'].sum().reset_index()
            sgbdf = df.groupby('Service')['Estimated Savings'].sum().reset_index()

            # fill in df values in worksheet
            self.insert_df_into_excel_summary_sheet(df=self.create_readme_sheet(), writer=writer_summary, sheetname=readme_worksheet_name, index=False)
            self.insert_df_into_excel_summary_sheet(df=ssdf, writer=writer_summary, sheetname=summary_sheet_name)
            self.insert_df_into_excel_summary_sheet(df=df, writer=writer_summary, sheetname=self.name_of_main_worksheet)
            self.insert_df_into_excel_summary_sheet(df=dgbdf, writer=writer_summary, sheetname=domain_sheet_name, index=False)
            self.insert_df_into_excel_summary_sheet(df=sgbdf, writer=writer_summary, sheetname=service_sheet_name, index=False)

            #formatting
            readme_worksheet.set_column('A:A', 120, workbook.add_format(workbook_format['large_description_format'])) #domain
            self.format_worksheet( df=df, workbook=workbook, worksheet=worksheet, workbook_format=workbook_format, name_xls_main_sheet=self.name_of_main_worksheet)
            self.add_savings_by_check_chart(df, workbook, summary_worksheet, name_xls_main_sheet=self.name_of_main_worksheet)
            domain_worksheet.set_column('A:A', 20, workbook.add_format(workbook_format['large_description_format'])) #domain
            domain_worksheet.set_column('B:B', 20, workbook.add_format(workbook_format['savings_format'])) #savings
            service_worksheet.set_column('A:A', 20, workbook.add_format(workbook_format['large_description_format'])) #service
            service_worksheet.set_column('B:B', 20, workbook.add_format(workbook_format['savings_format'])) #savings
            self.add_domain_savings_chart(dgbdf, workbook, summary_worksheet, domain_sheet_name, 'Savings by Domain', 'A46')
            self.add_domain_savings_chart(sgbdf, workbook, summary_worksheet, service_sheet_name, 'Savings by Tool Optimizer', 'J46')

            writer_summary.close()
        except Exception as exc:
             self.appConfig.console.print(f"[Red]Unable to create Summary XLS file on local folder: {exc}")
             self.logger.exception(exc)

class ReportOutputDisplayAlerts():
    # display alerts to console

    def __init__(self, appConfig) -> None:
        self.appConfig = appConfig

    def display_alerts_to_cli(self):
        pass
        # for alert in self.appConfig.alerts.keys():
        #     if self.appConfig.alerts[alert]:
        #         print(self.appConfig.alerts[alert])
