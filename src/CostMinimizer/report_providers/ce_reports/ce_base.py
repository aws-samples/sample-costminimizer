# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ...constants import __tooling_name__

import os
import sys
# Required to load modules from vendored subfolder (for clean development env)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "./vendored"))

import datetime
import logging
import pandas as pd
#For date
from dateutil.relativedelta import relativedelta
#For email
from abc import ABC
from pyathena.pandas.result_set import AthenaPandasResultSet
from ...report_providers.report_providers import ReportBase

class CeBase(ReportBase, ABC):
    """Retrieves BillingInfo checks from CostExplorer API
    >>> costexplorer = CostExplorer()
    >>> costexplorer.addReport(GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"}])
    """    
    def __init__(self, appConfig):
        
        super().__init__( appConfig)
        self.appConfig = appConfig

        #Array of reports ready to be output to Excel.
        try:
            self.client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('ce')
        except Exception as e:
            self.appConfig.console.print('\n[red]Unable to establish boto session for CostExplorer. \n{e}[/red]')
            sys.exit()

        self.end = datetime.date.today().replace(day=1)
        self.riend = datetime.date.today()
        #if CurrentMonth or CURRENT_MONTH:
        #    self.end = self.riend

        #if LAST_MONTH_ONLY:
        #    self.start = (datetime.date.today() - relativedelta(months=+1)).replace(day=1) #1st day of month a month ago
        #else:
            # Default is last 12 months
        self.start = (datetime.date.today() - relativedelta(months=+12)).replace(day=1) #1st day of month 12 months ago
    
        self.ristart = (datetime.date.today() - relativedelta(months=+11)).replace(day=1) #1st day of month 11 months ago
        self.sixmonth = (datetime.date.today() - relativedelta(months=+6)).replace(day=1) #1st day of month 6 months ago, so RI util has savings values
        try:
            self.accounts = self.getAccounts()
        except:
            logging.exception("Getting Account names failed")
            self.accounts = {}

        self.logger = logging.getLogger(__name__)
        self.reports = [] # returns list of report classes
        self.report_result = [] # returns list of report results
        self.reports_in_progress = []
        self.completed_reports = []
        self.failed_reports = []
        
        
        #CUR Reports specific variables 
        self.profile_name = None

        self.lookback_period = None
        self.output = None #output as json
        self.parsed_query = None #query after all substitutions and formating
        self.dependency_data= {}
        self.report_dependency_list = []  #List of dependent reports.

    @staticmethod
    def name():
        '''return name of report type'''
        return 'ce'

    def get_caching_status(self) -> bool:
        return True

    def post_processing(self):
        pass

    def auth(self):
        '''set authentication, we use the AWS profile to authenticate into the AWS account which holds the CUR/Athena integration'''
        self.profile_name = self.appConfig.customers.get_customer_profile_name(self.appConfig.customers.selected_customer)
        self.logger.info(f'Setting {self.name()} report authentication profile to: {self.profile_name}')

    def setup(self, run_validation=False):
        '''setup instrcutions for cur report type'''

        pass

    def run(
        self, 
        imported_reports=None, 
        additional_input_data=None, 
        expiration_days=None, 
        type=None,
        display=True,
        cow_execution_type=None) -> None:
        '''
        run ce report provider

        imported_reports = may be provided, if not provided will be discovered
        additional_input_data = additional input into the generation of the cache hash
        expiration_days = for cache expiration
        type = base or None; base tells this method that report is not a dependency for another report
        display = boolean; tells run() wether to display output on terminal with the rich module
        '''

        display=self.set_display() #set display variable

        self.reports = self.import_reports_for_run(imported_reports) #import reports

        self.expiration_days = self.set_expiration_days(expiration_days) #set expiration days

        self.accounts, self.regions, self.customer = self.set_report_request_for_run()

        self.provider_run(additional_input_data, display)

        return self.reports_in_progress

    def run_additional_logic_for_provider(self, report_object, additional_input_data=None) -> None:
        self.additional_input_data = additional_input_data

    def _set_report_object(self, report):
        '''set the report object for run'''
        
        return report(self.query_paramaters, self.appConfig.auth_manager.aws_cow_account_boto_session)

    def getAccounts(self):
        accounts = {}
        try:
            client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('organizations')
        except Exception as e:
            self.appConfig.console.print('\n[red]Unable to establish boto session for Organizations. \n{e}[/red]')
            sys.exit()

        paginator = client.get_paginator('list_accounts')
        response_iterator = paginator.paginate()
        for response in response_iterator:
            for acc in response['Accounts']:
                accounts[acc['Id']] = acc
        return accounts
    
    def addRiReport(self, Name='RICoverage', Savings=False, PaymentOption='PARTIAL_UPFRONT', Service='Amazon Elastic Compute Cloud - Compute'): #Call with Savings True to get Utilization report in dollar savings
        self.chart_type_of_excel = 'chart' #other options (table, pivot, chart)
        if Name == "RICoverage":
            results = []
            response = self.client.get_reservation_coverage(
                TimePeriod={
                    'Start': self.ristart.isoformat(),
                    'End': self.riend.isoformat()
                },
                Granularity='MONTHLY'
            )
            results.extend(response['CoveragesByTime'])
            while 'nextToken' in response:
                nextToken = response['nextToken']
                response = self.client.get_reservation_coverage(
                    TimePeriod={
                        'Start': self.ristart.isoformat(),
                        'End': self.riend.isoformat()
                    },
                    Granularity='MONTHLY',
                    NextPageToken=nextToken
                )
                results.extend(response['CoveragesByTime'])
                if 'nextToken' in response:
                    nextToken = response['nextToken']
                else:
                    nextToken = False
            
            rows = []
            for v in results:
                row = {'date':v['TimePeriod']['Start']}
                row.update({'Coverage%':float(v['Total']['CoverageHours']['CoverageHoursPercentage'])})
                rows.append(row)  
                    
            df = pd.DataFrame(rows)
            df.set_index("date", inplace= True)
            df = df.fillna(0.0)
            df = df.T
        elif Name in ['RIUtilization','RIUtilizationSavings']:
            #Only Six month to support savings
            results = []
            response = self.client.get_reservation_utilization(
                TimePeriod={
                    'Start': self.sixmonth.isoformat(),
                    'End': self.riend.isoformat()
                },
                Granularity='MONTHLY'
            )
            results.extend(response['UtilizationsByTime'])
            while 'nextToken' in response:
                nextToken = response['nextToken']
                response = self.client.get_reservation_utilization(
                    TimePeriod={
                        'Start': self.sixmonth.isoformat(),
                        'End': self.riend.isoformat()
                    },
                    Granularity='MONTHLY',
                    NextPageToken=nextToken
                )
                results.extend(response['UtilizationsByTime'])
                if 'nextToken' in response:
                    nextToken = response['nextToken']
                else:
                    nextToken = False
            
            rows = []
            if results:
                for v in results:
                    row = {'date':v['TimePeriod']['Start']}
                    if Savings:
                        row.update({'Savings$':float(v['Total']['NetRISavings'])})
                    else:
                        row.update({'Utilization%':float(v['Total']['UtilizationPercentage'])})
                    rows.append(row)  
                        
                df = pd.DataFrame(rows)
                df.set_index("date", inplace= True)
                df = df.fillna(0.0)
                df = df.T
                type = 'chart'
            else:
                df = pd.DataFrame(rows)
                type = 'table' #Dont try chart empty result
        elif Name == 'RIRecommendation':
            results = []
            response = self.client.get_reservation_purchase_recommendation(
                #AccountId='string', May use for Linked view
                LookbackPeriodInDays='SIXTY_DAYS',
                TermInYears='ONE_YEAR',
                PaymentOption=PaymentOption,
                Service=Service
            )
            results.extend(response['Recommendations'])
            while 'nextToken' in response:
                nextToken = response['nextToken']
                response = self.client.get_reservation_purchase_recommendation(
                    #AccountId='string', May use for Linked view
                    LookbackPeriodInDays='SIXTY_DAYS',
                    TermInYears='ONE_YEAR',
                    PaymentOption=PaymentOption,
                    Service=Service,
                    NextPageToken=nextToken
                )
                results.extend(response['Recommendations'])
                if 'nextToken' in response:
                    nextToken = response['nextToken']
                else:
                    nextToken = False
                
            rows = []
            for i in results:
                for v in i['RecommendationDetails']:
                    row = v['InstanceDetails'][list(v['InstanceDetails'].keys())[0]]
                    row['Recommended']=v['RecommendedNumberOfInstancesToPurchase']
                    row['Minimum']=v['MinimumNumberOfInstancesUsedPerHour']
                    row['Maximum']=v['MaximumNumberOfInstancesUsedPerHour']
                    row['Savings']=v['EstimatedMonthlySavingsAmount']
                    row['OnDemand']=v['EstimatedMonthlyOnDemandCost']
                    row['BreakEvenIn']=v['EstimatedBreakEvenInMonths']
                    row['UpfrontCost']=v['UpfrontCost']
                    row['MonthlyCost']=v['RecurringStandardMonthlyCost']
                    rows.append(row)  
                
                    
            df = pd.DataFrame(rows)
            df = df.fillna(0.0)
            self.chart_type_of_excel = 'table' #Dont try chart this
        else:
            df = pd.DataFrame()

        self.report_result.append({'Name':Name,'Data':df, 'Type':self.chart_type_of_excel})

    def addLinkedReports(self, Name='RI_{}',PaymentOption='PARTIAL_UPFRONT'):
        pass
            
    def addReport(self, Name="Default",GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"},], 
    Style='Total', NoCredits=True, CreditsOnly=False, RefundOnly=False, UpfrontOnly=False, IncSupport=False, IncTax=True):
        
        #GLOBALS
        SES_REGION = self.appConfig.config['ses_region']
        if not SES_REGION:
            SES_REGION="us-east-1"
        ACCOUNT_LABEL = os.environ.get('ACCOUNT_LABEL')
        if not ACCOUNT_LABEL:
            ACCOUNT_LABEL = 'Email'
            
        CURRENT_MONTH = self.appConfig.config['current_month']
        if CURRENT_MONTH == "True":
            CURRENT_MONTH = True
        else:
            CURRENT_MONTH = False

        LAST_MONTH_ONLY = self.appConfig.config['last_month_only']

        #Default exclude support, as for Enterprise Support
        #as support billing is finalised later in month so skews trends    
        INC_SUPPORT = os.environ.get('INC_SUPPORT')
        if INC_SUPPORT == "True":
            INC_SUPPORT = True
        else:
            INC_SUPPORT = False

        #Default include taxes    
        INC_TAX = os.environ.get('INC_TAX')
        if INC_TAX == "False":
            INC_TAX = False
        else:
            INC_TAX = True

        TAG_VALUE_FILTER = self.appConfig.config['costexplorer_tags_value_filter'] or '*'
        TAG_KEY = self.appConfig.config['costexplorer_tags']  

        self.chart_type_of_excel = 'chart' #other option table
        
        results = []
        if not NoCredits:
            response = self.client.get_cost_and_usage(
                TimePeriod={
                    'Start': self.start.isoformat(),
                    'End': self.end.isoformat()
                },
                Granularity='MONTHLY',
                Metrics=[
                    'UnblendedCost',
                ],
                GroupBy=GroupBy
            )
        else:
            Filter = {"And": []}

            Dimensions={"Not": {"Dimensions": {"Key": "RECORD_TYPE","Values": ["Credit", "Refund", "Upfront", "Support"]}}}
            if INC_SUPPORT or IncSupport: #If global set for including support, we dont exclude it
                Dimensions={"Not": {"Dimensions": {"Key": "RECORD_TYPE","Values": ["Credit", "Refund", "Upfront"]}}}
            if CreditsOnly:
                Dimensions={"Dimensions": {"Key": "RECORD_TYPE","Values": ["Credit",]}}
            if RefundOnly:
                Dimensions={"Dimensions": {"Key": "RECORD_TYPE","Values": ["Refund",]}}
            if UpfrontOnly:
                Dimensions={"Dimensions": {"Key": "RECORD_TYPE","Values": ["Upfront",]}}
            if "Not" in Dimensions and (not INC_TAX or not IncTax): #If filtering Record_Types and Tax excluded
                Dimensions["Not"]["Dimensions"]["Values"].append("Tax")

            tagValues = None
            if TAG_KEY:
                tagValues = self.client.get_tags(
                    SearchString=TAG_VALUE_FILTER,
                    TimePeriod = {
                        'Start': self.start.isoformat(),
                        'End': datetime.date.today().isoformat()
                    },
                    TagKey=TAG_KEY
                )

            if tagValues:
                Filter["And"].append(Dimensions)
                if len(tagValues["Tags"]) > 0:
                    Tags = {"Tags": {"Key": TAG_KEY, "Values": tagValues["Tags"]}}
                    Filter["And"].append(Tags)
            else:
                Filter = Dimensions.copy()

            response = self.client.get_cost_and_usage(
                TimePeriod={
                    'Start': self.start.isoformat(),
                    'End': self.end.isoformat()
                },
                Granularity='MONTHLY',
                Metrics=[
                    'UnblendedCost',
                ],
                GroupBy=GroupBy,
                Filter=Filter
            )

        if response:
            results.extend(response['ResultsByTime'])
     
            while 'nextToken' in response:
                nextToken = response['nextToken']
                response = self.client.get_cost_and_usage(
                    TimePeriod={
                        'Start': self.start.isoformat(),
                        'End': self.end.isoformat()
                    },
                    Granularity='MONTHLY',
                    Metrics=[
                        'UnblendedCost',
                    ],
                    GroupBy=GroupBy,
                    NextPageToken=nextToken
                )
     
                results.extend(response['ResultsByTime'])
                if 'nextToken' in response:
                    nextToken = response['nextToken']
                else:
                    nextToken = False
        rows = []
        sort = ''
        for v in results:
            row = {'date':v['TimePeriod']['Start']}
            sort = v['TimePeriod']['Start']
            for i in v['Groups']:
                key = i['Keys'][0]
                if key in self.accounts:
                    key = self.accounts[key][ACCOUNT_LABEL]
                row.update({key:float(i['Metrics']['UnblendedCost']['Amount'])}) 
            if not v['Groups']:
                row.update({'Total':float(v['Total']['UnblendedCost']['Amount'])})
            rows.append(row)  

        df = pd.DataFrame(rows)
        df.set_index("date", inplace= True)
        df = df.fillna(0.0)
        
        if Style == 'Change':
            dfc = df.copy()
            lastindex = None
            for index, row in df.iterrows():
                if lastindex:
                    for i in row.index:
                        try:
                            df.at[index,i] = dfc.at[index,i] - dfc.at[lastindex,i]
                        except:
                            logging.exception("Error")
                            df.at[index,i] = 0
                lastindex = index
        df = df.T
        df = df.sort_values(sort, ascending=False)

        self.report_result.append({'Name':Name,'Data':df, 'Type':self.chart_type_of_excel})
        
    def get_report_dataframe(self, columns=None) -> AthenaPandasResultSet:
        
        if self.dataframe is None:
            #data comes from query
            try:
                self.fetched_query_result = self.get_query_fetchall()
            except:
                self.fetched_query_result = None
        else:
            #data comes from cache
            self.fetched_query_result = self.dataframe

        return pd.DataFrame(self.fetched_query_result, columns=self.get_expected_column_headers())

    def generateExcel(self, writer):
        # Create a Pandas Excel writer using XlsxWriter as the engine.\
        workbook = writer.book

        for report in self.report_result:
            if report == [] or len(report['Data']) == 0:
                continue

            # Add a new worksheet after all existing worksheet
            # Get the number of existing worksheets
            num_worksheets = len(workbook.worksheets())

            worksheet = workbook.add_worksheet(report['Name'])

            report['Data'].to_excel(writer, sheet_name=report['Name'])

            if report['Type'] == 'chart':
                
                # Create a chart object.
                chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
                
                chartend=12
                if self.appConfig.config['current_month']:
                    chartend=13
                for row_num in range(1, len(report['Data']) + 1):
                    chart.add_series({
                        'name':       [report['Name'], row_num, 0],
                        'categories': [report['Name'], 0, 1, 0, chartend],
                        'values':     [report['Name'], row_num, 1, row_num, chartend],
                    })
                chart.set_y_axis({'label_position': 'low'})
                chart.set_x_axis({'label_position': 'low'})
                worksheet.insert_chart('O2', chart, {'x_scale': 2.0, 'y_scale': 2.0})
