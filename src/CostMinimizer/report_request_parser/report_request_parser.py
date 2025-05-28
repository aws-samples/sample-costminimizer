# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import logging
import json
from time import sleep
from ..utils.yaml_loader import import_yaml_file
from ..config.config import Config

class ReportRequestFileNotProvidedException(Exception):
    pass

class ReportRequestFileNotFoundException(Exception):
    pass

class ReportRequestMissingCustomerConfigurationException(Exception):
    pass

class CustomerDoesNotExistException(Exception):
    pass

class CustomerReportConfigurationErrorException(Exception):
    pass

class ReportsParse:
    '''
    Holds report request information for for any reports in the request file,
    report request may be submitted on via cli or as module
    '''
    
    def __init__(self, report_request) -> None:
        self.logger = logging.getLogger(__name__)
        self.report_request = report_request
        '''report naming standard: "report_name.suffix"'''

    def __repr__(self):
        return f"{self.get_all_reports()}"

    def _get_report_name(self, report) -> str:
        '''return report name w/o suffix'''
        return report.split('.')[0]
    
    def _get_report_type(self, report) -> str:
        '''return report suffix w/o name'''
        return report.split('.')[1]

    def _get_reports_enabled(self, report_type) -> list:
        '''return report list with only enabled reports'''
        enabled_reports = []
        
        for report, value in self.report_request.items():
            if self._get_report_type(report) == report_type:
                if value is True:
                    enabled_reports.append(self._get_report_name(report))

        return enabled_reports
    
    def _get_all_reports(self, report_type) -> list:
        '''return report names enabled or disabled'''
        all_reports = []
        
        for report, value in self.report_request.items():
            if self._get_report_type(report) == report_type:
                all_reports.append(self._get_report_name(report))

        return all_reports

    def get_all_reports(self) -> dict:
        '''return all reports as raw dict'''
        return self.report_request

    def get_all_enabled_reports(self) -> list:
        '''return a list of all enabled reports'''
        enabled_reports = {}
        for k,v in self.get_all_reports().items():
            if v is True:
                try:
                    report_name = k.split('.')[0]
                    report_type = k.split('.')[1]
                    enabled_reports[report_name] = report_type
                except:
                    continue 

        return enabled_reports

class CustomerParse:
    '''
    Holds customer information from report request,
    report request may be submitted on via cli or as module
    '''
    def __init__(self, appConfig, customer_request, selected_customer) -> None:
        self.logger = logging.getLogger(__name__)
        self.customer_request = customer_request
        self.selected_customer = selected_customer
        self.accepted_config = ['payer', 'domain', 'accounts']  
        self.accounts = [] 
        self.config = appConfig.config
    
    def determine_customer_configuration_type(self, customer_name) -> str:
        '''
        Return if customer is configured with payer|domain|accounts
        If multiple configured, we only care to return one
        '''

        try:
            configuration_type = [key for key in self.customer_request[customer_name].keys() if key in self.accepted_config]
        except:
            self.logger.error(f'CustomerDoesNotExistException: Customer {customer_name} does not exist.')
            raise CustomerDoesNotExistException(f'Selected customer {customer_name} does not exist.')
            
        if len(configuration_type) == 0:
            self.logger.error(f'CustomerReportConfigurationErrorException {customer_name} misconfigured.  Unable to find payer or accounts information.')
            raise CustomerReportConfigurationErrorException(f'Customer {customer_name} does not have payer or accounts section configured.')

        #accounts is the default if it exists
        if 'accounts' in configuration_type:
            return 'accounts'

        if 'payer' in configuration_type:
            return 'payer'
        else:
            self.logger.error(f'CustomerReportConfigurationErrorException {customer_name} misconfigured. Unable to find payer or accounts information.')
            raise CustomerReportConfigurationErrorException(f'Customer {customer_name} does not have payer or accounts section configured.')
        

    def get_all_customers(self) -> dict:
        '''return all customers raw dict'''
        return self.customer_request
    
    def get_all_customer_names(self) -> list:
        '''return all customer names'''
        return list(self.customer_request.keys())
    
    def get_customer_data(self, customer_name):
        '''return all data for the customer'''
        try:
            return self.customer_request[customer_name]
        except:
            raise CustomerDoesNotExistException(f'The customer {customer_name} does not exist.')

    def get_customer_profile_name(self, customer_name):
        '''return customer profile name or None if not configured'''
        customer_data = self.get_customer_data(customer_name)
        if 'profile' in customer_data.keys():
            return customer_data['profile']
        else:
            return None

    def get_customer_payer_account(self, customer_name) -> list:
        '''return customer payer id'''
        customer_data = self.get_customer_data(customer_name)
        #make sure we have payer information and / or account information
        self.determine_customer_configuration_type(customer_name)

        if 'payer' in customer_data:    
            return [customer_data['payer']]
        else:
            self.logger.error(f'CustomerReportConfigurationErrorException {customer_name}: Unable to find payer information.')
            raise CustomerReportConfigurationErrorException(f'Customer {customer_name} Unable to find payer information.')
        

    def get_customer_domain_name(self, customer_name) -> list:
        '''return customer domain name'''
        customer_data = self.get_customer_data(customer_name)
        if self.determine_customer_configuration_type(customer_name) == 'domain':
            return [customer_data['domain']]
        else:
            return []

    def get_customer_accounts(self, customer_name) -> list:
        '''return cusomer accounts'''
        customer_data = self.get_customer_data(customer_name)
        
        if 'accounts' not in customer_data.keys():
            return []
        
        return customer_data['accounts']

    def get_customer_min_spend_amount(self, customer_name) -> list:
        customer_data = self.get_customer_data(customer_name)

        if 'min_spend' not in customer_data.keys():
            return [0]

        return [customer_data['min_spend']]
    
    def set_customer_accounts(self, customer_name, accounts:list) -> None:
        '''input the selected linked accounts'''

        self.customer_request[customer_name]['accounts'] = accounts

    def set_customer_regions(self, customer_name, regions:list) -> None:
        '''input the selected customer regions'''

        self.customer_request[customer_name]['regions'] = regions

    def get_customer_regions(self, customer_name, excluded_regions=[]) -> list:
        '''return customer regions'''
        customer_data = self.get_customer_data(customer_name)

        if 'regions' not in customer_data.keys():
            return []

        return [r for r in customer_data['regions'] if r not in excluded_regions]

    # def get_customer_accounts(self) -> list:
    #     return self.accounts
        
class ToolingReportRequest:
    '''
    Parse the reports requested by user 
    return report ReportParse and CustomerParse objects 
    '''

    def __init__(self, report_request_input_file, read_from_database=False, reports_from_menu=None, selected_customer='') -> None:
        self.appConfig = Config()
        self.logger = logging.getLogger(__name__)
        self.report_request_input_file = report_request_input_file
        self.selected_customer = selected_customer
        self.report_request = {}
        self.reports_from_menu = reports_from_menu

        if read_from_database:
            self.appConfig.datasource = 'database'

        #reports defined in yaml file
        if self.appConfig.datasource == 'yaml':
            self.report_request = self.load_report_request_file()
        
            self.valid_report_sections = ['reports', 'customers']
            self.validate_report_sections(self.valid_report_sections)

            '''check if user-defined tags exist and set them in self.appConfig'''
            if "user_tags" in self.report_request:
                if self.report_request['user_tags'] != 'null' :
                    self.appConfig.using_tags = True
                    self.appConfig.user_tag_values = json.loads(self.report_request['user_tags'])
                else:
                    self.appConfig.using_tags = False
            else:
                self.appConfig.using_tags = False
            '''
            If using a report_request file check that the customer has been
            defined in the file.
            '''
            if not self.validate_customer_exists_in_report_request_file(self.report_request, self.selected_customer):
                self.logger.error(f'Using {self.report_request_input_file.resolve()} report_request file, customer {self.selected_customer} must be defined in the file.')
                raise CustomerDoesNotExistException(f'Using {self.report_request_input_file.resolve()} report_request file, customer {self.selected_customer} must be defined in the file.')

        '''
        load customer data from file; report request should only contain
        regions and accounts under the customer - the rest is loaded from 
        the database
        '''
        #reports coming only from menu items
        if self.appConfig.datasource == 'database':
            self.report_request['reports'] = self.reports_from_menu

        self.reports = ReportsParse(self.report_request['reports'])
        #self.customers = CustomerParse(self.report_request['customers'], self.selected_customer)

    def __repr__(self):
        return f"{self.reports_from_menu}"
    
    def load_report_request_file(self) -> dict:
            
        if self.appConfig.mode == 'cli':
            with self.config.console.status(f"Report Parser: Importing report request for customer: {self.selected_customer}"):
                sleep(1.5) #let user see progress
                try:
                    report_request = import_yaml_file(self.report_request_input_file)
                except FileNotFoundError as e:
                    self.logger.error(f'FileNotFoundError for {self.report_request_input_file}')
                    raise ReportRequestFileNotFoundException(f"{self.report_request_input_file} is not Found.")
        elif self.appConfig.mode == 'module':
            pass
        
        return report_request

    def _set_customer_request_from_database(self) -> dict:
        '''
        If customer comes from database; construct the customer request record.
        '''        
        #get customer record from database
        customer_from_database = self.appConfig.database.get_customer(self.selected_customer.strip())
        self.appConfig.database.email_address=customer_from_database[0].EmailAddress
        #customer names in the database should be unique
        if len(customer_from_database) != 1:
            self.logger.error(f'Requested customer {self.selected_customer} does not exist.')
            raise CustomerDoesNotExistException(f'Requested customer {self.selected_customer} does not exist.')

        #get customers payer number from database
        payer = self.appConfig.database.get_customer_payers(self.selected_customer.strip())
        #each customer should have a payer 
        if len(payer) == 0:
            self.logger.error(f'No payers fround for customer: {self.selected_customer}.')
            raise CustomerDoesNotExistException(f'No payers fround for customer: {self.selected_customer}.')

        payer = payer[0] #We currently only take the first payer returned TODO need to handle multiple payers

        if 'customers' not in self.report_request.keys():
            self.report_request['customers'] = {}

        if self.selected_customer not in self.report_request['customers'].keys():
            self.report_request['customers'][self.selected_customer] = {}
        
        #construct customer data dictionary 
        self.report_request['customers'][self.selected_customer]['payer'] = payer
        self.report_request['customers'][self.selected_customer]['id'] = customer_from_database[0].Id
        self.report_request['customers'][self.selected_customer]['email'] = customer_from_database[0][2]
        self.report_request['customers'][self.selected_customer]['profile'] = customer_from_database[0][5]
        self.report_request['customers'][self.selected_customer]['secret_name'] = customer_from_database[0][6]
        self.report_request['customers'][self.selected_customer]['cur_s3_bucket'] = customer_from_database[0][7]
        self.report_request['customers'][self.selected_customer]['cur_db'] = customer_from_database[0][8]
        self.report_request['customers'][self.selected_customer]['cur_table'] = customer_from_database[0][9]
        self.report_request['customers'][self.selected_customer]['cur_region'] = customer_from_database[0][10]
        self.report_request['customers'][self.selected_customer]['min_spend'] = customer_from_database[0][11]
        self.report_request['customers'][self.selected_customer]['regex'] = customer_from_database[0][12]

    def validate_report_sections(self, sections) -> None:
        '''assert that customers and reports sections exist and have data'''
        for section in sections:
            if section not in self.report_request.keys():
                self.logger.error(f'ReportRequestMissingCustomerConfigurationException section not found {section}')
                raise ReportRequestMissingCustomerConfigurationException(f'Report file missing {section} section.')
            
            if self.report_request[section] is None:
                self.logger.error(f'ReportRequestMissingCustomerConfigurationException section missing {section}')
                raise ReportRequestMissingCustomerConfigurationException(f'Report section {section} is misconfigured.')
    
    def validate_customer_exists_in_report_request_file(self, report_request, selected_customer) -> bool:

        if selected_customer in report_request['customers'].keys():
            return True
        else:
            return False

    def get_reports(self) -> ReportsParse:
        '''Return reports object'''
        return self.reports

    def get_customer(self) -> CustomerParse:
        '''return customer object'''
        return ''

    def get_all_reports(self):
        '''Return customer and reports objects'''
        return (self.get_customer(), self.get_reports())
    
        


