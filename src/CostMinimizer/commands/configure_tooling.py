# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import logging
import pandas as panda
from ..utils.cow_validations import aws_account_length, pad_aws_account
from ..security.cow_authentication import Authentication
from ..security.cow_encryption import CowEncryption
from ..utils.term_menu import launch_terminal_menu
from ..gexport_conf.gexport_conf import CowExportConf
from ..gimport_conf.gimport_conf import CowImportConf
import click
import tabulate as tabulate
import ast
import sys
import boto3

class ErrorInConfigureCowHelper(Exception):
    pass

class ErrorInConfigureCowInsertDB(Exception):
    pass

class UnableToWriteToAWSConfigFile(Exception):
    pass

class UnableToProcessInternalsConfigurationItem(Exception):
    pass

# Define ANSI escape codes for colors
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'  # Reset color

class ConfigureToolingCommand:

    def __init__(self, appInstance) -> None:
        self.appInstance = appInstance
        self.appConfig = appInstance.config_manager.appConfig

        self.logger = logging.getLogger(__name__)
        self.module_path =  self.appConfig.internals['internals']['reports']['reports_module_path']
        self.default_report_configs = []

    def run(self):
        if (self.appConfig.arguments_parsed.ls_conf):
            self.nice_display_aws_account_configured()
        elif (self.appConfig.arguments_parsed.auto_update_conf):
            self.automated_cow_configuration(auto=True)
        else:
            self.menu()

    def menu(self) -> None:
        list_menus = [
            "1)    Manual CostMinimizer Tool Configuration (setup my AWS account)",
            "2)    Automated CostMinimizer Tool Configuration",
            "3)    Update CostMinimizer Internals Configuration",
            "4)    Validate CostMinimizer configuration",
            "QUIT MENU"
        ]

        title = f'MAIN MENU '
        subtitle = f'Please use keys UP/DOWN to choose menu: '
        
        self.nice_display_aws_account_configured()

        while(True):
            # input text where caption has yellow background
            input("Press Enter to continue...")
            menu_txt, selection = launch_terminal_menu(list_menus, title=title, subtitle=subtitle, multi_select=False, show_multi_select_hint=False, show_search_hint=True)
                
            if selection == 0:
                self.automated_cow_configuration(auto=False)
            if selection == 1:
                self.automated_cow_configuration(auto=True)
            if selection == 2:
                self.automated_cow_internals_parameters()
            if selection == 3:
                self.validate_cow_configuration()
            if selection == 4:
                break
    
    def export_global_configuration(self):
        ce = CowExportConf(self.appConfig)
        ce.run()    
    
    def import_global_configuration(self):
        ci = CowImportConf(self.appConfig)
        ci.run()   
         
    def configure_report_parameters(self):
        #Get a list of reports
        selected_report = self.config_report_menu()
        #Pick report to configure
           
        report_name = selected_report.replace("'", "").strip()  
        report_parameters = self.appConfig.database.get_report_parameters(report_name)                
        self._configure_report_parameters(report_name, report_parameters)

        
    def _configure_report_parameters(self,report_name, report_parameters):
        '''display current parameters and user can change them to something new'''
        #[report_name:{'parameter_name':'value','current_value':'value','allowed_values':['val','val,'val']}]
        if report_parameters == []:
            for params in self.default_report_configs:
                try:
                    params = ast.literal_eval(params)
                    if list(params.keys())[0] == report_name:
                        report_parameters = params[report_name]
                except (ValueError, SyntaxError) as e:
                    self.logger.error(f"Error parsing default report config: {e}")
                    continue
        else:
            try:
                report_parameters = ast.literal_eval(report_parameters[0][0])
                report_parameters = report_parameters[report_name]
            except (ValueError, SyntaxError, IndexError, KeyError) as e:
                self.logger.error(f"Error parsing report parameters: {e}")
                return
  
        for param in report_parameters:
            try:
                idx = report_parameters.index(next(item for item in report_parameters if item["parameter_name"] == param["parameter_name"]))
                report_parameters[idx]["current_value"] = self.report_parameter_menu(param["allowed_values"], param["current_value"], param["parameter_name"])
            except StopIteration:
                self.logger.error(f"Error finding parameter: {param['parameter_name']}")
                continue
                
        self.appConfig.database.update_report_parameters(report_name, report_parameters)
        self.appConfig.console.print(f'[yellow]Parameters for report {report_name} have been updated.')
        '''write new values to database'''

    def clear_all_cache(self):
        cache_dir = self.appConfig.app_path / self.appConfig.internals['internals']['reports']['cache_directory']

        if cache_dir.is_dir():
            for file_path in cache_dir.glob('*_output_*.json'):
                file_path.unlink()
                print(f"Deleted file: {file_path}")
        else:
            print("Cache directory does not exist.")

    def nice_display_aws_account_configured(self, display_also=True) -> dict:
        '''Display customer selection menu;Return cx_id of selected customer to update'''

        #table_name = 'cow_configuration'
        
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
        
        aws_account_data = panda.DataFrame( [l_headers[1:]])
        return_aws_account_data = self.appConfig.database.get_cow_configuration() 
        aws_account_data.loc[1] = list(self.appConfig.database.get_cow_configuration()[0])[1:]
        
        if display_also:
            self.appConfig.console.print('[yellow]Existing configuration of the AWS account to access the data :')
            print(tabulate.tabulate(aws_account_data.transpose(), headers = l_headers, tablefmt='pretty', showindex="never"))

        return return_aws_account_data

    def get_config_report_menu_items(self):
        '''return a list of report menu items'''
        reports = self.appConfig.database.get_configurable_reports()
        self.default_report_configs = []
        
        for report in reports:  
            if report[1] == "True":
                self.default_report_configs.append(report[2])

        
        report_menu = [ f"{report[0]:<40} " for report in reports if report[1] =="True" ]
        
        return report_menu

    def config_report_menu(self) :
        '''display report menu and return selections'''
        reports = self.get_config_report_menu_items()
        
        title=f'Please select the report to configure:'
        subtitle = 'subtitle'
        terminal_menu = launch_terminal_menu(reports, title=title, subtitle=subtitle, multi_select=False, show_multi_select_hint=True, show_search_hint=True)
        #list_options = [i[0] for i in terminal_menu]
        list_options= terminal_menu[0]

        return list_options

    def report_parameter_menu(self, parameters, current_value, parameter_name) :
        '''display allowed parameters menu and return selection'''
       # parameters = params["allowed_values"]
        
        title=f'Please select a new value for [{parameter_name}]: Current value: [{current_value}]'
        subtitle = f'${current_value}'
        terminal_menu = launch_terminal_menu(parameters, title=title, subtitle=subtitle, multi_select=False, show_multi_select_hint=True, show_search_hint=True)
        #list_options = [i[0] for i in terminal_menu]
        list_options= terminal_menu[0]

        return list_options

    def get_report_menu_items(self):
        '''return a list of report menu items'''
        reports = self.appConfig.database.get_available_reports()
        
        # test id resports is not empty
        if not reports:
            self.appConfig.console.print("[red]Error : No reports found in the CostMinimizer database. Please check configuration file !")
            sys.exit(1)
        else:
            max_length = max(len(report[6]) for report in reports if report[5] in ['1','True'])
            report_menu = [ f"Name: {report[6][:max_length].ljust(max_length)} Svc: {report[4][:20]:<20} Type: {report[3][:4]:<4} Desc: {report[2][:80]:<80}" for report in reports if report[5] in ['1','True'] ]

        # insert item called 'ALL' at the beginning of the list report_menu
        report_menu.insert(0, f"Name: {'ALL'[:max_length].ljust(max_length)} Svc: {'ALL'[:20]:<20} Type: {'ALL'[:4]:<4} Desc: {'ALL'[:80]:<80}")
        return report_menu

    def report_menu(self) :
        '''display report menu and return selections'''
        reports = self.get_report_menu_items()
        
        title=f'Please select the reports to run (or select "Name: ALL" for all reports):'
        subtitle = 'subtitle'
        terminal_menu = launch_terminal_menu(reports, title=title, subtitle=subtitle, multi_select=True, show_multi_select_hint=True, show_search_hint=True)

        if isinstance(terminal_menu, list) and len(terminal_menu) > 0 and 'Name: ALL' in terminal_menu[0][0]:
            # If 'ALL' is selected, return all available reports
            list_options = reports[1:]
        else:
            list_options = [i[0] for i in terminal_menu]


        # Ensure required reports are included when --genai-recommendations is enabled
        # This is necessary for generating AI recommendations based on these specific reports
        if self.appConfig.arguments_parsed.genai_recommendations:
            TOTAL_ACCOUNTS_VIEW = "TOTAL /ACCOUNTS view"
            SERVICES_VIEW = "SERVICES view"
            TOTAL_ACCOUNTS_VIEW_LINE = "Name: TOTAL /ACCOUNTS view Svc: Cost Explorer Type: ce  Desc: Montly CostExplorer Accounts Total View"
            SERVICES_VIEW_LINE = "Name: SERVICES view Svc: Cost Explorer Type: ce Desc: Montly CostExplorer Services View"
            required_reports = []

            if TOTAL_ACCOUNTS_VIEW not in list_options:
                # add TOTAL_ACCOUNTS_VIEW in list list_options
                required_reports.append(TOTAL_ACCOUNTS_VIEW_LINE)
            if SERVICES_VIEW not in list_options:
                # add SERVICES_VIEW in list list_options
                required_reports.append(SERVICES_VIEW_LINE)

            # add required_reports in list_options
            list_options.extend(required_reports)

        return list_options

    def regions_menu(self, selected_accounts) :
        '''return list of regions'''
        regions =  self.appConfig.get_regions(selected_accounts=selected_accounts)

        title = 'Select one of the region (no impact on global checks like TA, CO and CE)'
        subtitle = '-'
        terminal_menu = launch_terminal_menu(regions, title=title, subtitle=subtitle, multi_select=False, show_multi_select_hint=True, show_search_hint=True)
        list_options = [terminal_menu[0]]

        return list_options
    
    def pptx_enable(self) -> tuple:
        '''return pptx report selection'''
        menu_items = ['Yes', f'No']

        title = 'Enable Powerpoint report'
        subtitle = 'Select Yes if you would like CostMinimizer to generate a Powerpoint presentation'
        terminal_menu = launch_terminal_menu(menu_items, title=title, subtitle=subtitle, multi_select=False, show_multi_select_hint=True, show_search_hint=True)

        return terminal_menu
    
    def pptx_menu(self, account_count) -> tuple:
        '''return pptx report selection'''
        menu_items = ['Powerpoint Report: All Linked Accounts Under Payer', f'Powerpoint Report: Selected Linked Accounts({account_count}) - (limit 200 accounts)']

        title = 'PowerPoint Report Selection:'
        subtitle = 'Select the Powerpoint report data settings for this report'
        terminal_menu = launch_terminal_menu(menu_items, title=title, subtitle=subtitle, multi_select=False, show_multi_select_hint=True, show_search_hint=True)

        return terminal_menu
    
    def pptx_charge_types(self) -> tuple:
        '''return pptx charge types to exclude from report'''
        menu_items = ['None', 'Tax', f'Support', 'Credit', 'Enterprise Discount Program Discount', 'Refund']

        title = 'PowerPoint Report: Exclude Charge Types'
        subtitle = 'Select Charge Types to exclude from the report'
        terminal_menu = launch_terminal_menu(menu_items, title=title, subtitle=subtitle, multi_select=True, show_multi_select_hint=True, show_search_hint=True, exit_when_finished=True)

        return terminal_menu
    
    def user_tags_menu(self, tag_title,user_tags_menu):
        '''return list of user tags'''
        if isinstance(user_tags_menu, list) is False:
            user_tags_menu = user_tags_menu['tag_name'].tolist()
        if tag_title is not None:
            title = tag_title
        else:
            title = 'Choose up to 3 tag keys'
        subtitle = 'subtitle'
        terminal_menu = launch_terminal_menu(user_tags_menu, title=title, subtitle=subtitle, multi_select=True, show_multi_select_hint=True, show_search_hint=True)
        list_options = [i[0] for i in terminal_menu]

        return list_options
    
    
    def insert_automated_configuration(self, configuration, configuration_type=None, **kwargs) -> None:
        '''
        insert automated configuration
        '''
        #update cow_configuration database table
        try:
            self.update_cow_configuration_record(configuration)
        except:
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

    # get the s3 setting parameter for current Athena configuration
    def get_s3_primary_workgroup_settings_athena( self):
        '''
        get s3 primary workgroup settings athena
        '''
        s3_output_location = ''

        try:
            # Create an Athena client
            athena_client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('athena', region_name='us-east-1')

            # Get the primary workgroup details
            response = athena_client.get_work_group(WorkGroup='primary')

            # Extract the S3 output location from the response
            s3_output_location = response['WorkGroup']['Configuration']['ResultConfiguration']['OutputLocation']
        except Exception as e:
            self.logger.exception('An error occurred during execution', e, stack_info=True, exc_info=True)
            raise e
        return s3_output_location

    # get the list of CUR databases in Athena default current user credentails
    # then display the list of databases and 
    # offer to the user the possibility to select one of the databases in the list using launch_terminal_menu
    def get_athena_cur_databases(self) -> tuple:
        '''return athena cur databases'''
        athena_cur_databases = []
        try:
            athena_client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('athena', region_name='us-east-1')
            response = athena_client.list_databases(
                CatalogName='AwsDataCatalog'
            )
            for database in response['DatabaseList']:
                athena_cur_databases.append(database['Name'])
        except Exception as e:
            self.logger.exception('An error occurred during execution', e, stack_info=True, exc_info=True)
            raise e

        title = 'Select Athena CUR database:'
        subtitle = 'subtitle'
        terminal_menu = launch_terminal_menu(athena_cur_databases, title=title, subtitle=subtitle, multi_select=True, show_multi_select_hint=True, show_search_hint=True, exit_when_finished=True)

        return terminal_menu

    # get the list of CUR tables in Athena default current user credentails
    # then display the list of tables and 
    # offer to the user the possibility to select one of the tables in the list using launch_terminal_menu
    def get_athena_cur_tables(self, pDatabaseName) -> tuple:
        '''return athena cur tables'''
        athena_cur_tables = []
        try:
            athena_client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('athena', region_name='us-east-1')
            response = athena_client.list_table_metadata(
                CatalogName='AwsDataCatalog',
                DatabaseName=pDatabaseName
            )
            for table in response['TableMetadataList']:
                athena_cur_tables.append(table['Name'])
        except Exception as e:
            self.logger.exception('An error occurred during execution', e, stack_info=True, exc_info=True)
            raise e

        title = 'Select Athena CUR table:'
        subtitle = 'subtitle'
        terminal_menu = launch_terminal_menu(athena_cur_tables, title=title, subtitle=subtitle, multi_select=True, show_multi_select_hint=True, show_search_hint=True, exit_when_finished=True)

        return terminal_menu


    # get list of users in IAM service for the default credentials and 
    # then display the list of users and 
    # offer to the user to selection on of the user in the list using launch_terminal_menu
    def get_iam_users_for_ses_service(self) -> tuple:
        '''return iam users'''
        iam_users = []
        try:
            iam = self.appConfig.auth_manager.aws_cow_account_boto_session.client('iam')
            response = iam.list_users()
            for user in response['Users']:
                iam_users.append(user['UserName'])
        except Exception as e:
            self.logger.exception('An error occurred during execution', e, stack_info=True, exc_info=True)
            raise e

        title = 'Select IAM user to use for SES grant access:'
        subtitle = 'subtitle'
        terminal_menu = launch_terminal_menu(iam_users, title=title, subtitle=subtitle, multi_select=True, show_multi_select_hint=True, show_search_hint=True, exit_when_finished=True)

        return terminal_menu

    # get list of SES origin email address from the existing SES configuration
    # offer to the user to selection on of the user in the list using launch_terminal_menu
    def get_ses_origin_email_addresses(self) -> tuple:
        '''return ses origin email addresses'''
        ses_origin_email_addresses = []
        try:
            ses = self.appConfig.auth_manager.aws_cow_account_boto_session.client('ses', region_name=self.appConfig.selected_regions[0])

            # List identities
            try:
                identities = ses.list_identities()['Identities']
            except Exception as e:
                self.appConfig.console.print(f'[red]ERROR: {e}[/red] !')
                sys.exit(0)
            
            for identitie in identities:
                # Get mail from attributes for the first identity
                ses_origin_email_addresses.append(identitie)

            if (ses_origin_email_addresses):
                title = 'Select SES origin email address:'
                subtitle = 'subtitle'
                terminal_menu = launch_terminal_menu(ses_origin_email_addresses, title=title, subtitle=subtitle, multi_select=True, show_multi_select_hint=True, show_search_hint=True, exit_when_finished=True)
        except Exception as e:
            raise e

        return terminal_menu

    # get default region from the current AWS users credentials
    def get_default_region(self) -> str:
        '''return default region'''
        region = ''
        try:
            region = boto3.session.Session().region_name or 'us-east-1'  # Provides default if None
        except Exception as e:
            self.logger.exception('An error occurred during execution', e, stack_info=True, exc_info=True)
            raise e
        return region

    # get default SMTP address server from the current user credentials
    def get_default_smtp_server(self, default_ses_region) -> str:
        '''return default smtp server'''
        smtp_server = ''
        try:
            # Get the AWS region
            region = default_ses_region
            
            # Construct the SMTP endpoint
            smtp_server = f"email-smtp.{region}.amazonaws.com"

        except Exception as e:
            raise e
        return smtp_server


    def automated_cow_configuration(self, auto=False):
        cow_config = self.appConfig
        config = {}

        if not auto:
            default_value = self.appConfig.config['aws_cow_account']
            config['aws_cow_account'] = click.prompt(f"{GREEN}Enter your main {YELLOW}AWS Account Number {GREEN}(a 12-digit account number){RESET}", default_value)
            #validate aws account number
            if not aws_account_length(config['aws_cow_account'] ):
                config['aws_cow_account'] = pad_aws_account(config['aws_cow_account'] )

            default_value = '' if self.appConfig.config['aws_cow_profile'] is None else self.appConfig.config['aws_cow_profile']
            config['aws_cow_profile'] = click.prompt(f"{GREEN}Enter the {YELLOW}name of the AWS profile {GREEN}to be used (in ~/.aws/cow_config file){RESET}", default_value)

            default_value = '' if self.appConfig.config['sm_secret_name'] is None else self.appConfig.config['sm_secret_name']
            config['sm_secret_name'] = click.prompt(f"{GREEN}Enter the {YELLOW}secret {GREEN}to use for encryption/decryption if activated (not activated in standard){RESET}", default_value)

            default_value = self.appConfig.config['output_folder']
            config['output_folder'] = click.prompt(f"{GREEN}Enter the {YELLOW}output folder path {GREEN}(results are saved into this folder){RESET}", default_value)

            default_value = self.appConfig.config['cur_db']
            if default_value is None or default_value == '':
                list_databases = self.get_athena_cur_databases()
                if list_databases:
                    default_value = list_databases[0][0]
            config['cur_db'] = click.prompt(f"{GREEN}Enter the {YELLOW}CUR Database name{GREEN}, for the CUR checks/requests (like 'customer_cur_data'){RESET}", default_value)

            default_value = self.appConfig.config['cur_table']
            if default_value is None or default_value == '':
                list_tables = self.get_athena_cur_tables(config['cur_db'])
                if list_tables:
                    default_value = list_tables[0][0]
            config['cur_table'] = click.prompt(f"{GREEN}Enter the {YELLOW}CUR Table name{GREEN}, for the CUR checks/requests{RESET}", default_value)

            default_value = self.appConfig.config['cur_region']
            if default_value == '':
                default_value = 'us-east-1'
            config['cur_region'] = click.prompt(f"{GREEN}Enter the {YELLOW}CUR region{GREEN}, for the CUR checks/requests{RESET}", default_value)

            default_value = self.appConfig.config['ses_send']
            config['ses_send'] = click.prompt(f"{GREEN}Enter the {YELLOW}SES DESTINATION email address {GREEN}, CostMinimizer results are sent to this email (optional){RESET}", default_value)

            default_value = self.appConfig.config['ses_from']
            if default_value == '':
                list_emails = self.get_ses_origin_email_addresses()
                if list_emails:
                    default_value = list_emails[0][0]
            config['ses_from'] = click.prompt(f"{GREEN}Enter the {YELLOW}SES SENDER origin email address {GREEN}, CostMinimizer results are sent using this origin email (optional){RESET}", default_value)

            default_value = self.appConfig.config['ses_region']
            if default_value == '':
                default_value = self.get_default_region()
            config['ses_region'] = click.prompt(f"{GREEN}Enter the {YELLOW}SES region{GREEN} where the Simple Email Server is running (like 'us-east-1'){RESET}", default_value)

            default_value = self.appConfig.config['ses_smtp']
            if default_value == '':
                default_value = self.get_default_smtp_server( config['ses_region'])
            config['ses_smtp'] = click.prompt(f"{GREEN}Enter the {YELLOW}SES email SMTP server{GREEN} where the Simple Email Server is running{RESET}", default_value)

            default_value = '' if self.appConfig.config['ses_login'] is None else self.appConfig.config['ses_login']
            if default_value == '':
                iam_users = self.get_iam_users_for_ses_service()
                if iam_users:
                    default_value = iam_users[0][0]
            config['ses_login'] = click.prompt(f"{GREEN}Enter the {YELLOW}SES Email LOGIN{GREEN} to access the Simple Email Server is running{RESET}", default_value)

            default_value = '' if self.appConfig.config['ses_password'] is None else self.appConfig.config['ses_password']
            config['ses_password'] = click.prompt(f"{GREEN}Enter the {YELLOW}SES Email PASSWORD{GREEN} to access the Simple Email Server is running{RESET}", default_value)

            default_value = self.appConfig.config['costexplorer_tags']
            config['costexplorer_tags'] = click.prompt(f"{GREEN}Enter the {YELLOW}costexplorer tags{GREEN}, a list of Cost Tag Keys (comma separated and optional){RESET}", default_value)

            default_value = self.appConfig.config['costexplorer_tags_value_filter']
            config['costexplorer_tags_value_filter'] = click.prompt(f"{GREEN}Enter the {YELLOW}costexplorer tags values filter{GREEN}, provide tag value to filter e.g. Prod*{RESET}", default_value)

            default_value = self.appConfig.config['graviton_tags']
            config['graviton_tags'] = click.prompt(f"{GREEN}Enter the {YELLOW}graviton tags{GREEN}, a list of Tag Keys (comma separated and optional){RESET}", default_value)

            default_value = self.appConfig.config['graviton_tags_value_filter']
            config['graviton_tags_value_filter'] = click.prompt(f"{GREEN}Enter the {YELLOW}graviton tag value filter{GREEN}, provide tag value to filter e.g. Prod*{RESET}", default_value)

            default_value = self.appConfig.config['current_month']
            config['current_month'] = click.prompt(f"{GREEN}Enter the {YELLOW}current month{GREEN}, true / false for if report includes current partial month{RESET}", default_value)

            default_value = self.appConfig.config['day_month']
            config['day_month'] = click.prompt(f"{GREEN}Enter the {YELLOW}day of the month{GREEN}, when to schedule a run. 6, for the 6th by default{RESET}", default_value)

            default_value = self.appConfig.config['last_month_only']
            config['last_month_only'] = click.prompt(f"{GREEN}Enter the {YELLOW}last month only{GREEN}, Specify true if you wish to generate for only last month{RESET}", default_value)

            default_value = self.appConfig.config['cur_s3_bucket']
            if default_value is not None or '???' in default_value:
                # read the value of 
                l_value = self.get_s3_primary_workgroup_settings_athena()
                if (l_value):
                    default_value = l_value
            config['cur_s3_bucket'] = click.prompt(f"{GREEN}Enter the {YELLOW}CUR S3 bucket{GREEN}, for the CUR checks/requests (like s3://bucket-sam-cur-1/')'{RESET}", default_value)

            default_value = self.appConfig.config['aws_cow_s3_bucket']
            config['aws_cow_s3_bucket'] = click.prompt(f"{GREEN}Enter the {YELLOW}S3 bucket name where the results are saved{GREEN} (like s3://bucket-sam-cur-1/') (optional){RESET}", default_value)

            self.update_cow_configuration_record(config)
        else:

            try:
                config['aws_cow_account']  = cow_config.automate_launch_cow_cust_configure()
            except:
                exit(0)

        if not config['aws_cow_account'] :
            self.appConfig.console.print("[red]Failed to retrieve account ID automatically.[/red]")
        else:

            self.appConfig.console.print(f"[green]Using account number: {config['aws_cow_account']}[/green]")

            validated_account = self.validate_cow_configuration(customer_name='aws_cow_account')

            if len(validated_account) > 0:
                if not validated_account[0]['credentials']:
                    print(f"Unable to validate account credentials and access for profile: {validated_account[0]['account']}; check midway; check that the account role is 'Admin'.")
        
            self.nice_display_aws_account_configured()
    
    def update_aws_cow_account_secret(self) -> None:
        '''update admin account secret'''
        
        print(f'WARNING: Updating the secret may cause use to lose access to historical data which has been encrypted with the old secret.')

        self.appConfig.configure_authentication_profiles()
        self.appConfig.configure_boto_session()
        self.appConfig.encryption = CowEncryption(self.appConfig, self.appConfig.auth_manager.aws_cow_account_boto_session)
        
        sm = click.prompt("Enter New Secret: ", confirmation_prompt=True, hide_input=True)

        try:
            #try to create the secret
            self.appConfig.encryption.update_aws_cow_account_secret(sm)
        except:
            if self.appConfig.mode == 'cli':
                try:
                    #creation may fail if secret exists, try to update
                    self.appConfig.encryption.update_aws_cow_account_secret(sm, update=True)
                except:
                    print('CowEncryption encountered an error when updating the secret.')
                    raise

    def update_values_recursive(self, dictionary):
        
        readonly_keys = ["column_group_by", "column_report_name", "column_savings", "version" ]
        
        for key, value in dictionary.items():
            if isinstance(value, dict):
                # If the value is a dictionary, recursively update its values
                dictionary[key] = self.update_values_recursive(value)
            else:
                # Perform the desired update operation on each non-dict value
                if (key not in readonly_keys):
                    new_value = click.prompt(f"{GREEN}Enter the new value of {YELLOW} {key} :{RESET}", default = value)

                    dictionary[key] = new_value  # Replace with your specific update operation
        return dictionary


    def automated_cow_internals_parameters(self) -> dict():
        
        new_dict = self.update_values_recursive(self.appConfig.internals)
        
        # save dict into table of the COW database
        self.appConfig.database.write_internals_parameters_table( new_dict)

        return new_dict

    def validate_cow_configuration(self, customer_name='All'):

        self.appConfig.console.print('[green]Running Account Credential Validations...')

        cow_authentication = Authentication()

        accounts_validated = []
        
        if customer_name == 'All' or customer_name == 'aws_cow_account':

            account_validations = {'account': None, 'credentials': None, 'role': None, 'description': None}
        
            aws_cow_profile_name = f"{self.appConfig.internals['internals']['boto']['default_profile_name']}_profile"

            account_validations['account'] = aws_cow_profile_name
            account_validations['description'] = f"Admin Account"

            if not cow_authentication.validate_account_credentials(aws_cow_profile_name):
                self.appConfig.console.print(f"Admin Account: [yellow]{aws_cow_profile_name} - [red]Error - Unable to validate account credentials or access for aws account.")
                account_validations['credentials'] = False
            else:
                self.appConfig.console.print(f"Admin Account: [yellow]{aws_cow_profile_name} - [green]Success - Able to retrieve account credentials and access for aws account.")
                account_validations['credentials'] = True

            accounts_validated.append(account_validations)
        return accounts_validated
