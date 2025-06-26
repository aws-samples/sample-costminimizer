# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import logging
import shutil
import sys
import os
from datetime import datetime
import pandas as pd

from ..config.config import Config
from ..metrics.metrics import CowMetrics
from ..error.error import CustomerNotFoundError
from ..security.cow_authentication import Authentication
from .configure_tooling import ConfigureToolingCommand
from ..utils.term_menu import clear_cli_terminal
from ..report_request_parser.report_request_parser import ToolingReportRequest
from ..report_controller.report_controller import CowReportController
from ..report_output_handler.report_output_pptx import ReportOutputPptxHandler
from ..report_controller.region_discovery_controller import RegionDiscoveryController
from ..report_controller.resource_discovery_controller import ResourceDiscoveryController
from ..report_output_handler.report_output_handler import ReportOutputExcel, ReportOutputMetaData, ReportOutputHandlerBase, ReportOutputDisplayAlerts

class ErrorInReportDiscovery(Exception):
    pass

class RunToolingRun:

    def __init__(self, appInstance, selected_reports=None, selected_accounts=None, selected_regions=None, report_request_mode=None, send_mail=None) -> None:
        self.logger = logging.getLogger(__name__)
        self.appInstance = appInstance
        self.appConfig = Config()
        
        self.selected_reports = selected_reports
        self.selected_accounts = selected_accounts
        self.appInstance.selected_regions = selected_regions
        self.report_request_mode = report_request_mode

        self.report_controller = None
        self.completion_time = None
        self.final_report_output_folder = None
        self.cm = None #hold metric data

        self.writer = None
        self.send_mail = send_mail

    def set_report_request_all(self) -> None:
        '''
        set customer and report requests, populate the 
        self.appConfig.customers, self.appConfig.reports variables

        '''

        if self.appConfig.mode == 'cli':
            '''
            In cli/menu mode menu_selected_reports is passed in as a launch_terminal_menu object
            which needs to be converted to a dict, such as:
            i.e.: {'ebs_unattached_volumes.k2': True, 'lambda_arm_savings.cur': True}
            '''
            reports = {}
            l_list_reports = [i.name(self) for i in self.appConfig.reports]
            for report_line in l_list_reports:
                report_name = report_line.strip()

                sql = f"select report_name, report_provider from cow_availablereports WHERE report_name = '{report_name}'"
                try:
                    result = self.appConfig.database.select_records(sql, rows="one")
                    report = result[0]
                    report_provider = result[1]
                    reports[f'{report}.{report_provider}'] = True
                except Exception as e:
                    ErrorInReportDiscovery(f'Unable to pull report name {report_name} from the sqllite database.')

            self.appConfig.customers, self.appConfig.reports = self.report_request_parse(reports)

    def set_report_request_arguments(self, selected_reports) -> None:
        '''
        set customer and report requests, populate the 
        self.appConfig.customers, self.appConfig.reports variables

        '''

        if self.appConfig.mode == 'cli':
            '''
            In cli/menu mode menu_selected_reports is passed in as a launch_terminal_menu object
            which needs to be converted to a dict, such as:
            i.e.: {'ebs_unattached_volumes.k2': True, 'lambda_arm_savings.cur': True}
            '''
            if selected_reports is None:
                # If running from YAML file this will come in as 'None' and that's ok
                reports=None
            else:
                reports = {}
                for report_line in selected_reports:
                    report_name = report_line.strip()

                    sql = f"select report_name, report_provider from cow_availablereports WHERE report_name = '{report_name}'"
                    try:
                        result = self.appConfig.database.select_records(sql, rows="one")
                        report = result[0]
                        report_provider = result[1]
                        reports[f'{report}.{report_provider}'] = True
                    except Exception as e:
                        ErrorInReportDiscovery(f'Unable to pull report name {report_name} from the sqllite database.')

            self.appConfig.customers, self.appConfig.reports = self.report_request_parse(reports)

    def set_report_request(self, menu_selected_reports) -> None:
        '''
        set customer and report requests, populate the 
        self.appConfig.customers, self.appConfig.reports variables

        '''

        if self.appConfig.mode == 'cli':
            '''
            In cli/menu mode menu_selected_reports is passed in as a launch_terminal_menu object
            which needs to be converted to a dict, such as:
            i.e.: {'ce_accounts.ce': True, 'ce_services.ce': True}
            '''
            if menu_selected_reports is None:
                # If running from YAML file this will come in as 'None' and that's ok
                reports=None
            else:
                reports = {}
                for report_menu_line in menu_selected_reports:
                    report_common_name = report_menu_line.split(':')[1].replace('Svc', '').strip()
                    report_provider = report_menu_line.split('Type:')[1].split('Desc:')[0].strip()

                    sql = f"select report_name from cow_availablereports WHERE common_name = '{report_common_name}'"
                    try:
                        result = self.appConfig.database.select_records(sql, rows="one")
                        report = result[0]
                        reports[f'{report}.{report_provider}'] = True
                    except:
                        ErrorInReportDiscovery(f'Unable to pull report name {report_common_name} from the sqllite database.')

            self.appConfig.customers, self.appConfig.reports = self.report_request_parse(reports)

        elif self.appConfig.mode == 'module':
            '''
            menu_selected_reports should be passed in as a dict of reports
            i.e.: {'ebs_unattached_volumes.k2': True, 'lambda_arm_savings.cur': True}
            '''

            self.appConfig.customers, self.appConfig.reports = self.report_request_parse(menu_selected_reports)
        
    def check_for_required_region(self):
        '''
        Certain reports such as trusted advisor typically run in us-east-1
        other reports require regions to be selected by the user
        '''
        enabled_reports = self.appConfig.reports.get_all_enabled_reports().keys()
        for report in self.appConfig.report_classes:
            report_instance = report(self.appConfig)
            if report_instance.name() in enabled_reports and report_instance.require_user_provided_region():
                return True
                       
        return False
    
    def set_user_tags_map(self) -> None:
        
        self.appConfig.user_tag_list = CowReportController(self.appConfig, self.writer)._get_user_tags()

    def report_controller_build(self, writer) -> CowReportController:
        return CowReportController(self.appConfig, writer)

    def run_generate_report_output(self, report_controller, completion_time) -> None:
        '''
        Generate report xlsx, metadata and csv data
        '''

        if self.appConfig.cow_execution_type == 'sync':
            self.logger.info(f'Generating Report Excel Output')
            s = datetime.now()
            roe = ReportOutputExcel(self.appConfig, report_controller.get_completed_reports_from_controller(), completion_time)

            #write main excel report
            roe.write_to_excel()

            self.final_report_output_folder = roe.report_directory #set report output structure

            t = datetime.now() - s
            self.logger.info(f'Finished Excel Report in {t.total_seconds()} seconds')

            self.logger.info(f'Generating Report Metadata Output')
            s = datetime.now()
            romd = ReportOutputMetaData(self.appConfig, report_controller.get_completed_reports_from_controller(), report_controller.get_failed_reports_from_controller(), completion_time, True, True)

            t = datetime.now() - s
            self.logger.info(f'Finished Writing Metadata in {t.total_seconds()} seconds')

            try:
                asts = ReportOutputPptxHandler(self.appConfig, report_controller.get_completed_reports_from_controller(), report_controller.get_failed_reports_from_controller(), self.appConfig.start)
                asts.run()

                asts.fill_in_ppt_report( self.final_report_output_folder)

            except Exception as e:
                self.logger.error(f'Error creating Powerpoint presentation: {e}')
                self.appConfig.console.print(f'')
                self.appConfig.console.print(f'[red][Error:] [green]Powerpoint presentation: {e}')

            # Check if results should be saved to S3
            self.use_s3_bucket = (hasattr(self.appConfig.arguments_parsed, 'bucket_for_results') and self.appConfig.arguments_parsed.bucket_for_results is not None) or (str(self.appConfig.internals['internals']['results_folder']['enable_bucket_for_results']).lower() in ('true', 'yes', '1', 't', 'y'))
            if self.use_s3_bucket:
                self.s3_bucket_name = self.appConfig.arguments_parsed.bucket_for_results if (hasattr(self.appConfig.arguments_parsed, 'bucket_for_results') and self.appConfig.arguments_parsed.bucket_for_results is not None) else self.appConfig.internals['internals']['results_folder']['bucket_for_results']

            # If using S3, create a temporary local structure that will be uploaded later
            if self.use_s3_bucket:
                self.logger.info(f"Results will be uploaded to S3 bucket: {self.s3_bucket_name}")

            # Upload to S3 if enabled
            if self.use_s3_bucket:
                s3_key = f"{self.appConfig.config['aws_cow_account']}_{os.path.basename(self.final_report_output_folder)}"
                romd.upload_to_s3(self.final_report_output_folder, s3_key, self.s3_bucket_name)

            return roe

    def run_display_alerts_to_cli(self, report_folder):

        try:
            # Create a slide for "AWS Account Not Part of AWS Organizations"
            # Add your code here to create the slide
            self.appConfig.console.print( f'[yellow]TIP :[/yellow] CostMinimizer allows you to use Gen AI to ask a question about your dataset =>')
            self.appConfig.console.print( f'   CostMinimizer -q "Based on the in the attached file, what is my top savings opportunity?" -f "{report_folder}"\n')
        except Exception as e:
            self.appConfig.logger.error(f"Error creating slide for AWS Account Not Part of AWS Organizations: {str(e)}")
            # Handle the error appropriately

        ReportOutputDisplayAlerts(self.appConfig).display_alerts_to_cli()

    def run_end_of_app(self, cm, report_controller, completion_time) -> None:
        '''capture closing times in log and output metrics'''
        self.logger.info(f'Total report time: {str(cm.duration)}')
        self.appConfig.console.print(f'Total report time: {str(cm.duration)}')

    def make_log_file_copy(self, report_controller, completion_time, ) -> None:
        '''
        Make a copy of the cow log file into the report directory
        '''

        report_directory = ReportOutputHandlerBase(
        self.appConfig,
        report_controller.get_completed_reports_from_controller(), 
        completion_time
        ).get_report_directory()

        self.output_folder = self.appConfig.report_output_directory

        cow_log = self.appConfig.report_directory / self.appConfig.internals['internals']['logging']['log_file']
        dst_cow_log = report_directory / self.appConfig.internals['internals']['logging']['log_file']
        if not report_directory.is_dir():
            os.mkdir(report_directory.resolve())

        shutil.copyfile(cow_log.resolve(), dst_cow_log.resolve())
    
    def _set_report_request_mode(self, mode) -> None:
        '''set report request mode and log'''

        self.logger.info(f'Setting app mode to {mode}.')
        self.appConfig.report_request_mode = mode
    
    def check_report_request_mode(self) -> str:
        '''
        check for mode type and call function to set mode.  mode type are:

        default: report_request file is included in the default location
        file: report_request file is passed on the command line
        menu: user is asked on the command line to select report criteria
        browser: user is using the browser to select report criteria
        '''

        self.logger.info(f'Discovering app mode....')
        if self.appConfig.default_report_request.is_file():
            self._set_report_request_mode('default')
        else:
            self._set_report_request_mode('menu')

        return self.appConfig.report_request_mode

    def display_available_reports_menu(self):
        '''display a selectable menu of reports'''

        menu = ConfigureToolingCommand().report_menu()

        return menu

    def display_regions_menu(self, selected_accounts, requires_region_selection=False) -> list:
        '''display regions menu; return region list'''
        # If region is specified via command line, use it
        if self.appConfig.selected_regions:
            return self.appConfig.selected_regions
        
        # If --co is not used, skip region selection
        if not requires_region_selection:
            self.logger.info("Region selection skipped: --co option were not used")
            # Use default region, specified in Config()
            return self.appConfig.default_selected_region
        else:
            self.logger.info("Displaying region selection menu")
            menu_regions = ConfigureToolingCommand().regions_menu(selected_accounts)

            selected_regions = []
            for region in menu_regions:
                region_id = region.split(':')[0].strip()
                selected_regions.append(region_id)
            
        self.logger.info(f"Selected regions: {selected_regions}")
        return selected_regions[0]

    def display_pptx_menu(self, selected_accounts):
        '''display powerpoint report menu'''
        num_selected_accounts = len(selected_accounts)

        pptx_enable = ['Yes']

        if pptx_enable[0] == 'Yes':

            if self.appConfig.mode == 'cli':
                pptx_selection = ConfigureToolingCommand().pptx_menu(num_selected_accounts)
                # pptx_selection = ['', 1]
                if pptx_selection[1] == 0:
                    self.appConfig.pptx_report = 'payer'
                elif pptx_selection[1] == 1:
                    self.appConfig.pptx_report = 'linked_accounts'
                else:
                    self.appConfig.pptx_report = 'linked_accounts' #make payer the default
                    self.logger.error('Invalid PPTX report selection.')

                pptx_charge_types = ConfigureToolingCommand().pptx_charge_types()

                #make list of all selected values
                self.appConfig.pptx_charge_types = [ct[0] for ct in pptx_charge_types]

                #If None is selected; supply empty list
                if len(self.appConfig.pptx_charge_types) == 1 and self.appConfig.pptx_charge_types[0] == 'None':
                    self.appConfig.pptx_charge_types = []
                elif len(self.appConfig.pptx_charge_types) > 1:
                    #Remove any 'None' values
                    if 'None' in self.appConfig.pptx_charge_types:
                        self.appConfig.pptx_charge_types.remove('None')
            if self.appConfig.mode == 'module': #TODO this selection needs to go into the GUI 
                self.appConfig.pptx_report = 'payer'
                self.appConfig.pptx_charge_types = ['Tax', 'Support', 'Credit', 'Refund']

        return

    def _get_cur_user_tags(self,menu_user_tags)-> list:
        tag_list=[]
        for k2_tag in menu_user_tags:
            out = self.appConfig.user_tag_list.loc[self.appConfig.user_tag_list['tag_name'].eq(k2_tag).idxmax(),'normalized_key']
            tag_list.append(out)

        return tag_list

    def display_user_tags_menu(self) -> None:
        menu_user_tags = ConfigureToolingCommand().user_tags_menu(None, self.appConfig.user_tag_list)

        while len(menu_user_tags)>3:
            #prompt and re-ask if too many selected
            #self.appConfig.config.console.print(f'Please select a maximum of 3 tags: {len(menu_user_tags)} tags selected.')
            menu_user_tags = ConfigureToolingCommand().user_tags_menu(f'Please select a maximum of 3 tags. {len(menu_user_tags)} tags selected.', self.appConfig.user_tag_list)

        self.appConfig.user_tags =menu_user_tags
        self.appConfig.user_tag_values =[]
        self.appConfig.cur_user_tags = self._get_cur_user_tags(menu_user_tags)
        #loop over the tags key list as get all possible tag values from CUR. 
        tag_data_values = CowReportController(self.appConfig, self.writer)._get_user_tag_values(self.appConfig.cur_user_tags)

        for tag in menu_user_tags:
            
            #select the tag values from each tag key, removing duplicates and sorting alphabetically
            temp_cur_list =[]
            temp_cur_list.append(tag)
            cur_tag = self._get_cur_user_tags(temp_cur_list)
            tag_list = tag_data_values[cur_tag[0]].tolist()
            tag_list = list(dict.fromkeys(tag_list))
            tag_list.sort(key=str.lower)
            selected_tags = ConfigureToolingCommand().user_tags_menu(tag,tag_list)
            #tag_dict ={cur_tag[0] : selected_tags,'k2_tag':tag}
            tag_dict ={'cur_tag':cur_tag[0],'tag_list': selected_tags,'k2_tag':tag}
            self.appConfig.user_tag_values.append(tag_dict)

    def insert_at_top_of_dataframe(self, new_row, data_df) -> pd.DataFrame:
        new_data_df = pd.concat([new_row, data_df[:]]).reset_index(drop = True)

        return new_data_df

    def validate_boto_profile_connections(self, profile_name, profile_type='aws_credentials'):

        cow_authentication = Authentication()

        msg = f'Unable to make connection to admin account (aws account): profile: {profile_name}'

        try:
            if not cow_authentication.validate_account_credentials(profile_name):
                #unable to make connection to profile
                self.logger.info(msg)

                sys.exit(0)
            else:
                msg = f'Validated connection to aws account profile {profile_name}'
                self.logger.info(msg)
        except Exception as e:
            self.appConfig.console.print('[red]'+str(e.e).replace('\\n','').replace('\\r','').replace("b'","").replace("'",""))
            return False

        return True

    def validate_customer_name(self, customer_name) -> bool:
        try:
            if self.appConfig.database.get_customer_id(customer_name) is None:
                raise CustomerNotFoundError('', self.appConfig)
            return True
        except CustomerNotFoundError as e:
            self.logger.error(f"Customer not found: {customer_name}")
            return False

    def display_accounts_menu(self) -> list:
        '''display accounts menu; return selected accounts'''
        return self.appConfig.config['aws_cow_account']
    
    def report_request_parse(self, parsed_reports_from_menu=None) -> tuple:
        """
        Parse the report request.

        :param parsed_reports_from_menu: Reports parsed from the menu
        :return: Tuple containing parsed report information
        """
        ''' parse and return report request'''

        datasource = 'database'
        datasource_file = self.appConfig.database.database_file.resolve()
        if self.appConfig.mode == 'cli':
            '''
            In cli mode - we first check if there is a report request yaml file provided with the -f option.
            Next we check if there is a report request file in the default location.
            Else we check for the report request specified on the command line.
            '''
            try:
                if self.appConfig.default_report_request.is_file():
                    #Try file from the cow_internals default location
                    datasource = 'yaml'
                    report_request = ToolingReportRequest(self.appConfig.default_report_request)
                    datasource_file = self.appConfig.default_report_request
                else:
                    #Try with data from report and customer input menus
                    report_request = ToolingReportRequest(
                        self.appConfig.default_report_request,
                        read_from_database=True,
                        reports_from_menu=parsed_reports_from_menu
                        )

                if self.appConfig.debug:
                    print(f'[blue underline]Report data source from {datasource} : {datasource_file}')

                self.logger.info(f'Running in {self.appConfig.mode} mode: Report data source from {datasource} : {datasource_file}')
                return report_request.get_all_reports()
            except IOError as e:
                self.logger.error(f"Error accessing file: {str(e)}")
                raise
            except Exception as e:
                self.logger.error(f"Error creating ToolingReportRequest: {str(e)}")
                raise
        elif self.appConfig.mode == 'module':
            #Try with data from report and customer input menus
            report_request = ToolingReportRequest(
                self.appConfig.default_report_request,
                read_from_database=True,
                reports_from_menu=parsed_reports_from_menu
                )

            self.logger.info(f'Running in {self.mode} mode: Report data source from {datasource} : {datasource_file}')
            return report_request.get_all_reports()
    
    def set_using_tags_from_arguments(self):
        '''set if tags have been enabled on cli'''
        self.appConfig.using_tags = False
        if hasattr(self.appConfig.arguments_parsed, 'usertags') and (self.appConfig.arguments_parsed.usertags is True):
            self.appConfig.using_tags = True

    def run(self):

        '''
        Cow request mode is caputure in self.appConfig.mode and may be:
        cli: cow is started on the command line
        module: cow is imported and run as a module from within another program
        '''
        try:
            c = self.appConfig.auth_manager.aws_cow_account_boto_session.client('sts')
            c.get_caller_identity()
        except Exception as e:
            raise

        self.set_using_tags_from_arguments()

        self.report_controller = self.report_controller_build(self.writer)
        self.report_controller._controller_setup()

        # Get a list of available regions from the account
        # display message for the user to wait that getting list of regions is ongoing
        self.logger.info(f"Getting list of available regions for the admin account. Please wait...")
        self.appConfig.account_region_discovery = RegionDiscoveryController()
        self.appConfig.account_region_discovery.set_discovered_regions()

        # run preconditioned reports
        # display message for the user to wait that getting list of preconditionned reports is ongoing
        self.logger.info(f"Getting list of preconditionned reports for the admin account. Please wait...")
        self.appConfig.precondition_reports = ResourceDiscoveryController()
        self.appConfig.customers, self.appConfig.reports = self.report_request_parse(self.appConfig.precondition_reports.precondition_reports)
        self.appConfig.precondition_reports.run(self.report_controller)
        
        if self.appConfig.mode == 'cli':

            # define self.appConfig.reports list
            self.check_report_request_mode()

            menu_selected_reports = None
            if self.appConfig.arguments_parsed.checks:
                # Use the checks provided via command line
                if ('ALL' in self.appConfig.arguments_parsed.checks):
                    l_list_reports =  [i.name(self) for i in self.appConfig.reports]
                else:
                    l_list_reports = self.appConfig.arguments_parsed.checks
                #sef customer and report requests
                self.set_report_request_arguments(l_list_reports)

            elif self.appConfig.report_request_mode == 'menu':
                # Display reports menu - only if report request is not coming from YAML file or GUI
                menu_selected_reports = self.display_available_reports_menu()

                #sef customer and report requests
                self.set_report_request(menu_selected_reports)
                
                clear_cli_terminal(self.appConfig.mode)

            #validate admin account connection 
            # profile_name = f"{self.appConfig.internals['internals']['boto']['default_profile_name']}_profile"

            requires_region_selection = self.check_for_required_region()

            #display accounts menu
            selected_accounts = self.display_accounts_menu()
            
            # Check if region selection is required (--co options)
            #self.appConfig.reports.requires_region_selection() #chris
            if requires_region_selection:
                self.appConfig.console.print(f"\nRegion selection is required for --co (Compute Optimizer) option.")
            else:
                self.appConfig.console.print(f"\nRegion selection is not required for --ce, --ta, --cur options: Using default region: us-east-1")
                
            self.appConfig.selected_regions = self.display_regions_menu(selected_accounts, requires_region_selection)
            self.appConfig.selected_region = self.appConfig.selected_regions

            #run report controller run method
            self.report_controller.run()

            if self.appConfig.cow_execution_type == 'sync':
                #fetch data
                with self.appConfig.console.status(f'Fetching report results from providers (this may take a while)...'):
                    self.report_controller.fetch()

                #calculate savings
                with self.appConfig.console.status(f'Calculating savings (this may take a while)...'):
                    self.report_controller.calculate_savings()

                #save reports
                with self.appConfig.console.status(f'Fetching calculated reports from providers...'):
                    self.report_controller.get_provider_reports()

                self.appConfig.end = datetime.now()
                self.appInstance.end = self.appConfig.end

                #run CostOptimizer metrics
                self.cm = self.run_tooling_metrics(self.report_controller.all_providers_completed_reports)

            #hand data over to output 
            self.completion_time = datetime.now()         
            l_message = 'Generating reports to output folders...'
            if self.appConfig.arguments_parsed.genai_recommendations:
                l_message = l_message + ' including AI recommendations which may take some time...'
            with self.appConfig.console.status( l_message):
                l_roe = self.run_generate_report_output(self.report_controller, self.completion_time)

            self.appConfig.end = datetime.now()
            self.appInstance.end = self.appConfig.end

            #display any alerts to the cli
            self.run_display_alerts_to_cli( l_roe.output_filename)

            self.run_end_of_app(self.cm, self.report_controller, self.completion_time)

            #make a copy of the log file in the report directory
            self.make_log_file_copy(self.report_controller, self.completion_time)

    def run_tooling_metrics(self, completed_reports) -> CowMetrics:
        '''generate cow metrics'''
        cm = CowMetrics(self.appConfig, 'end')

        metric = {'version': self.appConfig.internals['internals']['version'] }
        cm.submit(metric)

        #number of selected accounts
        metric = {'number_of_accounts': 1}
        cm.submit(metric)

        #number of selected regions
        metric = {'number_of_regions': 1}
        cm.submit(metric)

        # Region
        metric = {'regions': 'us-east-1'}
        cm.submit(metric)

        #start and end times
        metric = {'start': self.appConfig.start.strftime("%Y-%m-%d %H:%M:%S"), 'end': self.appConfig.end.strftime("%Y-%m-%d %H:%M:%S") }
        cm.submit(metric)

        #runnning mode and installation type
        metric = { 'mode': self.appConfig.mode, 'installation_type': self.appConfig.installation_type }
        cm.submit(metric)

        #platform
        metric = { 'platform': self.appConfig.platform }
        cm.submit(metric)

        #Reports and estimated savings
        metric = {}
        metric['reports'] = {}
        total_savings = float(0.0)
        for report in completed_reports:

            l_savings = report.get_estimated_savings( sum=True)
            metric['reports'][report.name()] = l_savings
            # check if report.get_estimated_savings() return a numeric
            try:
                total_savings = total_savings + l_savings
            finally:
                self.logger.info(f'total_savings = {l_savings} via {report.name()}.get_estimated_savings()')

        cm.submit(metric)

        #total savings
        metric = {'total_savings': total_savings}
        cm.submit(metric)

        #total run duration
        cm.set_running_time(self.appConfig.start, self.appConfig.end)

        return cm
