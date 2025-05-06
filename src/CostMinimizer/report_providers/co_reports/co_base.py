# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"
from ...constants import __tooling_name__, __estimated_savings_caption__

import os
import sys
import datetime
import logging
import pandas as pd
#For date
from dateutil.relativedelta import relativedelta
from abc import ABC
from pyathena.pandas.result_set import AthenaPandasResultSet
from ...report_providers.report_providers import ReportBase
import boto3
from typing import List, Dict, Any
from dataclasses import dataclass
import numpy as np
import json
from rich.progress import track

# Required to load modules from vendored subfolder (for clean development env)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "./vendored"))
logger = logging.getLogger(__name__)


class EbsVolumesCache:

    def __init__(self) -> None:
        self.cache = {}
    
    def check_if_cache_value_exists(self, account_id, region, volumeType):
        if account_id in self.cache.keys():
            if region in self.cache[account_id].keys():
                if volumeType in self.cache[account_id][region].keys():
                    return True
                else:
                    return False 
            else:
                self.cache[account_id][region] = {}
                return False
        else:
            self.cache[account_id] = {}
            self.cache[account_id][region] = {}
            return False

    def add_volume_to_cache(self, account_id, region, volumeType, volumeApiResult):
        self.cache[account_id][region][volumeType] = volumeApiResult

        if volumeType in self.cache[account_id][region].keys():
            return True
        else:
            return False

    def get_value_from_cache(self, account_id, region, volumeType):
        return self.cache[account_id][region][volumeType]

class PricingQuery:
    def __init__(self, account_number, region, service_code, **term_matches):
        self.account_number = account_number
        
        # NOTE -- currently only us-east-1 region is supported with this API
        self.region = region
        self.service_code = service_code
        
        # Setup API client 
        session = boto3.Session(region_name=self.region)
        self.client = session.client('pricing')
        
        # Pre load the list of attributes for the service
        self.__service_attributes = None
        self.attr_filters = self.__convert_term_matches(term_matches)

    def __convert_term_matches(self, term_dict):
        result = []
        for (k,v) in term_dict.items():
            result.append({'Type': 'TERM_MATCH', 'Field': k, 'Value': v})
        return result
            
    def run(self, **term_matches):       
        if len(term_matches) > 0:
            filter_list = self.__convert_term_matches(term_matches)
        else:
            filter_list = self.attr_filters
        
        results = self.client.get_products(
            ServiceCode=self.service_code,
            Filters=filter_list
        )
        return results['PriceList']

@dataclass
class InstanceResults:
    data_frame: Any = None

    def create_plots(self):
        df = self.data_frame
        if df.size:
            return [df.pivot_table(
                columns=['accountName'],
                index='instanceType',
                values='storageCost', 
                aggfunc=np.sum).plot.bar(
                    title='Total Storage Cost of instances per account',  
                    stacked=True)]
        return None

class InstanceReport:
    name = "EC2 Instances All"
    fields = [
        'accountId',
        'accountName',
        'region',
        'instanceId',
        'Tenancy',
        'AZ',
        'status',
        'instanceType',
        'isClassic',
        'name',
        'platform',
        'LaunchedOn',
        'isSpot',
        'tags_list',
        'storageSize',
        'storageCost',
        'monthlyCost'
    ]

    def __init__(self):
        self.custom_results = InstanceResults

    def get_region_description(self, region_code):
        REGION_NAMES = {
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'EU (Ireland)',
            'eu-west-2': 'EU (London)',
            'eu-west-3': 'EU (Paris)',
            'eu-central-1': 'EU (Frankfurt)',
            'eu-north-1': 'EU (Stockholm)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)',
            'ap-northeast-2': 'Asia Pacific (Seoul)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-southeast-2': 'Asia Pacific (Sydney)',
            'ap-south-1': 'Asia Pacific (Mumbai)',
            'sa-east-1': 'South America (São Paulo)',
            'ca-central-1': 'Canada (Central)'}

        session = boto3.Session()
        regions = session.get_available_regions('ec2')
        
        # Using ec2 client to get region names
        ec2 = boto3.Session().client('ec2', region_code)
        response = ec2.describe_regions(RegionNames=[region_code], AllRegions=True)
        
        if response['Regions']:
            return REGION_NAMES.get(region_code, region_code)
        return None

    def get_ebs_volume_cost(self, ebs_volume_cache, account_id, ebs_type, size_in_gb, region, ebs_iops=None):
        gb_price = 0
        iops_price = 0
        gp3_baseline_iops = 3000
        io2_tier_1_iops = 32000
        io2_tier_2_iops = 64000
        #region_name = self.get_region_description(region)

        if ebs_volume_cache.check_if_cache_value_exists(account_id, region, ebs_type):
            price_list = ebs_volume_cache.get_value_from_cache(account_id, region, ebs_type)
            #print(ebs_type + ' Cache Hit')
        else:
            query = PricingQuery(account_number=account_id, 
                                region='us-east-1', 
                                service_code='AmazonEC2', 
                                volumeApiName=ebs_type, 
                                regionCode=region )
            price_list = query.run()
            ebs_volume_cache.add_volume_to_cache(account_id, region, ebs_type, price_list)
            
        ebs_dict = {}
        ebs_dict['ebs_type'] = ebs_type
        if len(price_list) > 0:
            for price_items in price_list:
                price_item = json.loads(price_items)
                terms = price_item["terms"]
                term = list(terms["OnDemand"].values())[0]
                price_dimension = list(term["priceDimensions"].values())[0]
                price = price_dimension['pricePerUnit']["USD"]
                if 'group' in price_item['product']['attributes']:
                    ebs_dict[price_item['product']['attributes']['group']] = price
                else:
                    ebs_dict[price_item['product']['productFamily']] = price


        ## Storage price
        
        if 'Storage' in ebs_dict:
            gb_price = float(ebs_dict['Storage']) * int(size_in_gb)


        ## IOPS price 

        ### For GP3

        if ebs_dict['ebs_type'] == 'gp3':
            if int(ebs_iops) > gp3_baseline_iops:
                net_iops = int(ebs_iops) - gp3_baseline_iops
                iops_price = float(ebs_dict['EBS IOPS']) * net_iops

        ### For IO1

        if ebs_dict['ebs_type'] == 'io1':
            iops_price = float(ebs_dict['EBS IOPS']) * ebs_iops
    

        ### For IO2

        if ebs_dict['ebs_type'] == 'io2':
            
            if int(ebs_iops) <= io2_tier_1_iops:
                iops_price = float(ebs_dict['EBS IOPS']) * int(ebs_iops)

            elif int(ebs_iops) > io2_tier_1_iops and int(ebs_iops) <= io2_tier_2_iops:

                iops_price_tier_1 = float(ebs_dict['EBS IOPS']) * io2_tier_1_iops
                

                net_iops_tier_2 = int(ebs_iops) - io2_tier_1_iops
                iops_price_tier_2 = float(ebs_dict['EBS IOPS Tier 2']) * net_iops_tier_2

                iops_price = iops_price_tier_1 + iops_price_tier_2
            
            else:

                iops_price_tier_1 = float(ebs_dict['EBS IOPS']) * io2_tier_1_iops

                net_iops_tier_2 = io2_tier_2_iops - io2_tier_1_iops
                iops_price_tier_2 = float(ebs_dict['EBS IOPS Tier 2']) * net_iops_tier_2

                
                net_iops_tier_3 = int(ebs_iops) - io2_tier_2_iops
                iops_price_tier_3 = float(ebs_dict['EBS IOPS Tier 3']) * net_iops_tier_3

                iops_price = iops_price_tier_1 + iops_price_tier_2 + iops_price_tier_3

        return round(iops_price + gb_price, 2)


    def get_instance_price(self, instance_type, operating_system, account_id, region, license_model="No License Required", tenancy="Shared"):
        # operating_system types: Windows, SUSE, RHEL, NA, Linux
        # license model options:
        # Bring your own license
        # No License Required
        # TODO calcluate based on license model and pre-installedsw like SQL Server
        region_name = self.get_region_description(region)

        #print(f"looking up prices for {instance_type}; {operating_system}; {region_name}; {tenancy}")
        #pricing_client = boto3.client('pricing')
        query = PricingQuery(account_number=account_id,
                            region='us-east-1',  # Since this is for the API endpoint, must be USE1
                            service_code='AmazonEC2',
                            location=region_name,
                            operatingSystem=f"{operating_system[0].upper()}{operating_system[1:]}",
                            capacitystatus='Used',
                            tenancy=tenancy,
                            instanceType=instance_type,
                            licenseModel=license_model,
                            preInstalledSw='NA'
                            )

        #print(f"pricing response: {response}")
        price_list = query.run()
        #print(price_list)
        if len(price_list) > 0:
            price_item = json.loads(price_list[0])
            terms = price_item["terms"]
            term = list(terms["OnDemand"].values())[0]
            price_dimension = list(term["priceDimensions"].values())[0]
            price = price_dimension['pricePerUnit']["USD"]
            return round(float(price)*730, 2)
        else:
            return 0.0

    def calculate_ebs_size_and_cost(self, instance: Dict[str, Any], region: str, client):
        total_size = 0
        total_cost = 0.0
        volume_ids = []
        account_id = instance.get('accountId')
        devices = instance.get('BlockDeviceMappings', [])
        
        if devices:
            for device in devices:
                vol_id = device.get('Ebs', {}).get('VolumeId', None)
                if vol_id:
                    volume_ids.append(vol_id)
            try:
                # Create a new boto3 session and EC2 client
                session = boto3.Session()
                ec2_client = session.client('ec2', region_name=region)
                
                response = ec2_client.describe_volumes(VolumeIds=volume_ids)
                volumes_info = response.get('Volumes', [])
                
                ebs_volume_cache = EbsVolumesCache()

                for vol_info in volumes_info:
                    vol_size = vol_info['Size']
                    vol_cost = self.get_ebs_volume_cost(
                        ebs_volume_cache, 
                        account_id,
                        vol_info['VolumeType'],
                        vol_size,
                        region,
                        vol_info.get('Iops', 0)
                    )
                    total_size += float(vol_size)
                    total_cost += float(vol_cost)
            except Exception as ex:
                logger.error(
                    f"Error getting volume size/cost info for {account_id}/{region}/{volume_ids}, {str(ex)}"
                )

        return total_size, total_cost

    def _get_account_name(self, account_id):
        # get the account alias of the current boto session
        try:
            iam_client = boto3.client('iam')
            response = iam_client.list_account_aliases()
            aliases = response.get('AccountAliases', [])
            if aliases:
                return aliases[0]
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting account alias: {str(e)}")

    def _convert_filters(self, filters):
        # convert filters to boto3 format
        aws_filters = []
        for f in filters:
            aws_filters.append({'Name': f['name'], 'Values': f['values']})
        return aws_filters

    # get platform type for a specific instanceId
    def get_platform(self, instance_id, region):

        # Create boto3 EC2 client 
        ec2_client = boto3.client('ec2', region_name=region)

        response = ec2_client.describe_instances(InstanceIds=[instance_id])

        platformDetails = response['Reservations'][0]['Instances'][0].get('PlatformDetails', 'N/A')
        architecture = response['Reservations'][0]['Instances'][0].get('Architecture', 'N/A')
        ebsOptimized = response['Reservations'][0]['Instances'][0].get('EbsOptimized', 'N/A')
        rootDeviceName = response['Reservations'][0]['Instances'][0].get('RootDeviceName', 'N/A')
        
        return platformDetails, architecture, ebsOptimized, rootDeviceName

    def list_ebs_instances_prices(self, region, account, filters: List[Dict[str, Any]] = None, 
                    get_storage_pricing: bool = True, 
                    get_instance_pricing: bool = True, display = False, report_name = '') -> List[Dict[str, Any]]:
        if filters is None:
            filters = []
            
        account_id = account
        # Get the account alias of the current boto3 session
        account_name = self._get_account_name(account_id)  
        
        # Create boto3 EC2 client 
        ec2_client = boto3.client('ec2', region_name=region)
        
        try:
            # Convert filters format if needed
            aws_filters = self._convert_filters(filters)
            
            # Using standard boto3 EC2 API call
            response = ec2_client.describe_instances(Filters=aws_filters)
            instances_list = []

            if display:
                display_msg = f'[green]Running Cost & Usage Report: {report_name} / {region}[/green]'
            else:
                display_msg = ''
            for reservation in track(response.get('Reservations', []), description=display_msg):
                for instance in reservation.get('Instances', []):
                    if instance['State']['Name'] in ['running', 'stopped']:
                        instance_info = {
                            'AZ': instance['Placement']['AvailabilityZone'],
                            'isClassic': instance.get('VpcId') is None,
                            'status': instance['State']['Name'],
                            'name': 'None'
                        }
                        
                        # Extract instance name from tags
                        tags = instance.get('Tags', [])
                        for tag in tags:
                            if tag['Key'] == 'Name':
                                instance_info['name'] = tag['Value']
                                break
                                
                        # Add the rest of the instance information
                        instance_info.update({
                            'accountId': account_id,
                            'accountName': account_name,
                            'region': region,
                            'instanceId': instance['InstanceId'],
                            'Tenancy': instance['Placement']['Tenancy'],
                            'instanceType': instance['InstanceType'],
                            'platform': instance.get('Platform', 'linux'),
                            'LaunchedOn': instance['LaunchTime'].isoformat(),
                            'isSpot': 'InstanceLifecycle' in instance and instance['InstanceLifecycle'] == 'spot',
                            'tags_list': tags
                        })
                        
                        if get_storage_pricing:
                            storage_size, storage_cost = self.calculate_ebs_size_and_cost(
                                instance, region, ec2_client
                            )
                            instance_info['storageSize'] = storage_size
                            instance_info['storageCost'] = storage_cost
                            
                        if get_instance_pricing:
                            instance_info['monthlyCost'] = self.get_instance_price(
                                instance_info['instanceType'], instance_info['platform'], 
                                instance_info['accountId'], instance_info['region']
                            )
                            
                        instances_list.append(instance_info)
                        
            return instances_list
            
        except Exception as ex:
            logger.error(f"Error processing EC2 instances for {account_id}/{region}: {str(ex)}")
            return []

    def get_instance_cost(self, instance_id, Cost_type = 'UnblendedCost'):
        ce_client = boto3.client('ce')
        
        # Set time range for last 30 days
        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        
        try:
            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='MONTHLY',
            Filter={
                'And': [
                    {
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': ['Amazon Elastic Compute Cloud - Compute']
                        }
                    },
                    {
                        'Tags': {
                            'Key': 'Name',
                            'Values': [instance_id]
                        }
                    }
                ]
            },
            Metrics=[Cost_type]  # or 'BlendedCost' or 'AmortizedCost'
            )
            
            # Get the cost from the response
            if response['ResultsByTime']:
                cost = 0.0
                currency = 'USD'
                # loop on each ResultsByTime
                for l in response['ResultsByTime']:
                    cost = cost + float(response['ResultsByTime'][0]['Total'][Cost_type]['Amount'])
                    currency = response['ResultsByTime'][0]['Total'][Cost_type]['Unit']
            return cost, currency

            
        except Exception as e:
            print(f"Error getting cost for instance {instance_id}: {str(e)}")
            return None, None

    # Combine both APIs to get recommendations and costs
    def get_recommendations_with_costs( self, region, account, display = True, report_name = '') -> List[Dict[str, Any]]:

        co_client = boto3.client('compute-optimizer', region_name=region)

        try:
            recommendations = co_client.get_ec2_instance_recommendations()

            instances_list = []

            if display:
                display_msg = f'[green]Running Cost & Usage Report: {report_name} / {region}[/green]'
            else:
                display_msg = ''
            for recommendation in track(recommendations['instanceRecommendations'], description=display_msg):

                instance_id = recommendation['instanceArn'].split('/')[-1]
                current_type = recommendation['currentInstanceType']
                finding = recommendation['finding']
                platform_details, architecture, ebsOptimized, rootDeviceName = self.get_platform( instance_id, region)

                # Get actual cost
                cost, currency = self.get_instance_cost(instance_id)

                # Print savings opportunities
                for option in recommendation['recommendationOptions']:
                    savings = option.get('savingsOpportunity', {})
                    reco_instance_type = option.get('instanceType', 'Not Available')
                    monthly_savings = savings.get('estimatedMonthlySavings', {})
                    savings_value = monthly_savings.get('value', 0)
                    migration_effort = option.get('migrationEffort', 'Not Available')
                    break

                instance_info = {
                    'instanceId': instance_id,
                    'currentInstanceType': current_type,
                    'platformDetails' : platform_details,
                    'recommendInstanceType': reco_instance_type,
                    'finding': finding,
                    'migrationEffort': migration_effort,
                    'savingsValue': savings_value,
                    'monthlyCost': cost,
                    'currency': currency,
                    'estimatedMonthlySavingsAmount' : savings_value
                }

                instances_list.append(instance_info)

            return instances_list

        except Exception as e:
            print(f"Error: {str(e)}")


class CoBase(ReportBase, ABC):
    """Retrieves BillingInfo checks from ComputeOptimizer API
    """    
    def __init__(self, appConfig):

        super().__init__( appConfig)
        self.appConfig = appConfig

        self.end = datetime.date.today().replace(day=1)
        self.riend = datetime.date.today()
        self.start = (datetime.date.today() - relativedelta(months=+12)).replace(day=1) #1st day of month 12 months ago
    
        self.ristart = (datetime.date.today() - relativedelta(months=+11)).replace(day=1) #1st day of month 11 months ago
        self.sixmonth = (datetime.date.today() - relativedelta(months=+6)).replace(day=1) #1st day of month 6 months ago, so RI util has savings values
        try:
            self.accounts = self.getAccounts()
        except:
            logging.exception("Getting Account names failed")
            self.accounts = {}

        self.reports = [] # returns list of report classes
        self.report_result = [] # returns list of report results
        self.reports_in_progress = []
        self.completed_reports = []
        self.failed_reports = []

        self.ESTIMATED_SAVINGS_CAPTION = __estimated_savings_caption__
        
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
        return 'co'

    def get_caching_status(self) -> bool:
        return True

    def post_processing(self):
        pass

    def auth(self):
        '''set authentication, we use the AWS profile to authenticate into the AWS account which holds the CUR/Athena integration'''
        self.profile_name = self.appConfig.customers.get_customer_profile_name(self.appConfig.customers.selected_customer)
        logger.info(f'Setting {self.name()} report authentication profile to: {self.profile_name}')
    
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
            self.appConfig.console.print('\n[red]Unable to establish boto session for Organizations.  \n{e}[/red]')
            sys.exit()

        paginator = client.get_paginator('list_accounts')
        response_iterator = paginator.paginate()
        for response in response_iterator:
            for acc in response['Accounts']:
                accounts[acc['Id']] = acc
        return accounts

    def addCoReport(self, range_categories, range_values, list_cols_currency, group_by): #Call with Savings True to get Utilization report in dollar savings
        self.graph_range_values_x1, self.graph_range_values_y1, self.graph_range_values_x2,  self.graph_range_values_y2 = range_values
        self.graph_range_categories_x1, self.graph_range_categories_y1, self.graph_range_categories_x2,  self.graph_range_categories_y2 = range_categories
        self.list_cols_currency = list_cols_currency
        self.group_by = group_by
        # insert pivot type of graphs in the excel worksheet
        self.set_chart_type_of_excel()
        return self.report_result

    def get_query_fetchall(self) -> list:
        return self.get_query_result()

    def get_query_result(self) -> AthenaPandasResultSet:
        '''return pandas object from pyathena async query'''

        try:
            result = self.report_result[0]['Data']
        except Exception as e:
            msg = f'Unable to get query result self.report_result[0]: {e}'
            self.logger.error(msg)
            self.set_fail_query(reason=msg)
            result = None
        
        return result

    def get_report_dataframe(self, columns=None) -> AthenaPandasResultSet:
        
        try:
            self.fetched_query_result = self.get_query_fetchall()
        except:
            self.fetched_query_result = None

        return pd.DataFrame(self.fetched_query_result, columns=self.get_expected_column_headers())

    def set_workbook_formatting(self) -> dict:
        # set workbook format options
        fmt = {
            'savings_format': {'num_format': '$#,##0.00'},
            'default_column_format': {'align': 'left', 'valign': 'bottom', 'text_wrap': True},
            'large_description_format': {'align': 'left', 'valign': 'bottom', 'text_wrap': True},
            'comparison_column_format': {'num_format': '$#,##0', 'bold': True, 'font_color': 'red','align': 'right', 'valign': 'right', 'text_wrap': True},
            'header_format': {'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BC', 'border': 1}
        }
        return fmt

    def generateExcel(self, writer):
        # Create a Pandas Excel writer using XlsxWriter as the engine.\
        workbook = writer.book
        workbook_format = self.set_workbook_formatting()

        for report in self.report_result:
            if report == [] or len(report['Data']) == 0:
                continue

            report['Name'] = report['Name'][:31]
            worksheet_name = report['Name']
            df = report['Data']

            # Add a new worksheet
            worksheet = workbook.add_worksheet(report['Name'])

            # Convert specific columns to numeric type before writing
            for col in self.list_cols_currency:
                try:
                    df[df.columns[col-1]] = pd.to_numeric(df[df.columns[col-1]], errors='coerce')
                except:
                    continue

            df.to_excel(writer, sheet_name=report['Name'])

            # Format workbook columns in self.list_cols_currency as money
            for col_idx in self.list_cols_currency:
                col_letter = chr(65 + col_idx)
                worksheet.set_column(f"{col_letter}:{col_letter}", 30, workbook.add_format(workbook_format['savings_format']))

            if self.chart_type_of_excel == 'chart':
                
                # Create a chart object.
                chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
                
                NumLines=len(report['Data'])
                chart.add_series({
                    # Cell = line:0-Col0 => estimatedMonthlySavingsAmount column header
                    'name':       [report['Name'], 0, 0],
                    # Range = [line:Col to Line:LAST_LINE-col] => currentInstanceType column values
                    'categories': [report['Name'], self.graph_range_categories_y1, self.graph_range_categories_x1, self.graph_range_categories_y2, self.graph_range_categories_x2 ],      
                    # Range = [line:Col to Line:LAST_LINE-col] => estimatedMonthlySavingsAmount column values
                    'values':     [report['Name'], self.graph_range_values_y1, self.graph_range_values_x1, NumLines, self.graph_range_values_x2],      
                })
                chart.set_y_axis({'label_position': 'low'})
                chart.set_x_axis({'label_position': 'low'})
                worksheet.insert_chart('O2', chart, {'x_scale': 2.0, 'y_scale': 2.0})

            elif self.chart_type_of_excel == 'pivot':

                # define the minimum value for the potential_savings to be displayed in the pivot graph
                self.min_savings_to_display = 0

                # Create pivot chart for potential savings by instance type
                pivot_data = (df.groupby([df.columns[i] for i in self.group_by])
                              .sum([df.columns[self.graph_range_values_x1-1]])
                              .reset_index()
                              #.query(f"`{df.columns[self.graph_range_values_x1-1]}` > {self.min_savings_to_display}")
                              .sort_values(by=df.columns[self.graph_range_values_x1-1], ascending=False, na_position='last'))

                if not pivot_data.empty:
                    # Create a new worksheet for the chart
                    l_name_of_worksheet = f'{worksheet_name} - GroupBy'
                    chart_sheet = workbook.add_worksheet(l_name_of_worksheet[:31])
                    if report['DisplayPotentialSavings'] is True:
                        l_name_of_column = 'Potential Savings'
                    else:
                        l_name_of_column = 'Total Costs'

                    # Write the pivot data to the worksheet
                    index_col = 0
                    for col in self.group_by:
                        list_values = [x for x in pivot_data[df.columns[col]].values]
                        chart_sheet.write_column(f'{chr(65+index_col)}1', ['GroupBy'] + list_values)
                        index_col = index_col + 1
                    list_savings = [float(x) for x in pivot_data[df.columns[self.graph_range_values_x1-1]].values]
                    chart_sheet.write_column(f'{chr(65+index_col)}1', [l_name_of_column] + list_savings)

                    # Create a new chart object
                    chart = workbook.add_chart({'type': 'column'})

                    # Configure the chart
                    chart.add_series({
                        'name': l_name_of_column,
                        'categories': f'=\'{worksheet_name} - GroupBy\'!$A$2:${chr(65+len(self.group_by)-1)}${len(pivot_data) + 1}',
                        'values': f'=\'{worksheet_name} - GroupBy\'!${chr(66+len(self.group_by)-1)}$2:${chr(66+len(self.group_by)-1)}${len(pivot_data) + 1}',
                        'data_labels': {'value': True, 'num_format': '$#,##0'},
                    })

                    # Set chart title and axis labels
                    l_name_of_worksheet = f'{worksheet_name} GroupBy'
                    chart.set_title({'name': l_name_of_worksheet[:31]})
                    chart.set_x_axis({'name': 'GroupBy'})
                    chart.set_y_axis({'name': f'{l_name_of_column} ($)', 'num_format': '$#,##0'})

                    # Insert the chart into the worksheet
                    chart_sheet.insert_chart('D2', chart, {'x_scale': 2, 'y_scale': 1.5})
                    return