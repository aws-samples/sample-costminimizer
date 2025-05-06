# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"
from ....constants import __tooling_name__

from ..co_base import CoBase

import boto3
import pandas as pd
from rich.progress import track

class CoInstancesreport(CoBase):

    def get_report_parameters(self) -> dict:

        #{report_name:[{'parameter_name':'value','current_value':'value','allowed_values':['val','val','val']} ]}
        return {'Compute Optimizer View':[{'parameter_name':'lookback_period','current_value':30,'allowed_values':['1','2','3','4','5']} ]}

    def set_report_parameters(self,params)    -> None:
        ''' Set the parameters to values pulled from DB'''

        param_dict = self.get_parameter_list(params)
        self.lookback_period = int(param_dict['Compute Optimizer View'][0]['current_value'])

    def supports_user_tags(self) -> bool:
        return True

    def is_report_configurable(self) -> bool:
        return True

    def author(self) -> list: 
        return ['slepetre']

    def name(self): #required - see abstract class
        return 'co_instancesreport'

    def common_name(self) -> str:
        return 'COMPUTE OPTIMIZER view'

    def service_name(self):
        return 'Compute Optimizer'

    def domain_name(self):
        return 'COMPUTE'

    def description(self): #required - see abstract class
        return '''Compute Optimizer recommendations.'''

    def long_description(self):
        return f'''AWS Compute Optimizer Main View:
        This report provides an overview of AWS Compute Optimizer recommendations for your resources.
        Compute Optimizer uses machine learning to analyze your resource utilization metrics and identify optimal AWS Compute resources.
        The report includes:
        - Recommendations for EC2 instances, EBS volumes, Lambda functions, and ECS services
        - Potential performance improvements and cost savings
        Use this view to identify opportunities for rightsizing your resources, improving performance, and reducing costs across your AWS infrastructure.'''

    def _set_recommendation(self):
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing compute optimizer. See the report for more details.'''

    def get_report_html_link(self) -> str:
        '''documentation link'''
        return '#'

    def report_type(self):
        return 'processed'

    def report_provider(self):
        return 'co'

    def savings_plan_enabled(self) -> bool:
        if 'savings_plan_savings_plan_a_r_n' in self.columns:
            return True

        return False

    def reservations_enabled(self) -> bool:
        if 'reservation_reservation_a_r_n' in self.columns:
            return True

        return False

    def get_required_columns(self) -> list:
        return ['accountId', 'region', 'instanceName', 'finding', 'recommendation', 'migrationEffort', 'platformDifferences', 'platformDetails', self.ESTIMATED_SAVINGS_CAPTION]


    def get_expected_column_headers(self) -> list:
        return ['accountId', 'region', 'instanceName', 'finding', 'recommendation', 'migrationEffort', 'platformDifferences', 'platformDetails', self.ESTIMATED_SAVINGS_CAPTION]

    def disable_report(self) -> bool:
        return False

    def display_in_menu(self) -> bool:
        return True

    def override_column_validation(self) -> bool:
        #see description in parent class
        return True

    def get_estimated_savings(self, sum=False) -> float:
        self._set_recommendation()

        return self.set_estimate_savings()

    def set_estimate_savings(self, sum=False) -> float:

        df = self.get_report_dataframe()

        if sum and (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
            return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))

        return 0.0

    def count_rows(self) -> int:
        '''Return the number of rows found in the dataframe'''
        try:
            return self.report_result[0]['Data'].shape[0]
        except Exception as e:
            self.appConfig.console.print(f"Error in counting rows: {str(e)}")
            return 0

    def calculate_savings(self):
        return 0.0

    def enable_comparison(self) -> bool:
        return False

    def get_comparison_definition(self) -> dict:
        '''Return dictionary of values required for comparison engine to function'''
        return { 
            'CSV_ID' : self.name(),
            'CSV_TITLE' : self.common_name(),
            'CSV_COLUMNS' : self.get_expected_column_headers(),
            'CSV_COLUMN_SAVINGS' : None,
            'CSV_GROUP_BY' : [],
            'CSV_COLUMNS_XLS' : [],
            'CSV_FILENAME' : self.name() + '.csv'
        }             

    def sql(self, client, region, account, display = False, report_name = ''): #required - see abstract class
        type = 'chart' #other option table
        results = []

        response = client.get_ec2_instance_recommendations()

        #print(response)
        recommendation_list = response['instanceRecommendations']
        data_list = []
        
        # Create EC2 client to get instance details
        # Create boto3 EC2 client 
        ec2_client = boto3.client('ec2', region_name=region)

        if display:
            display_msg = f'[green]Running Cost & Usage Report: {report_name} / {region}[/green]'
        else:
            display_msg = ''
        for recommendation in track(recommendation_list, description=display_msg):
                data_dict = {}
                data_dict['accountId'] = recommendation['accountId']
                data_dict['region'] = recommendation['instanceArn'].split(':')[3]
                data_dict['instanceName'] = recommendation['instanceName']
                data_dict['currentInstanceType'] = recommendation['currentInstanceType']
                data_dict['finding'] = recommendation['finding']
                
                # Get instance ID from ARN
                instance_id = recommendation['instanceArn'].split('/')[-1]
                
                try:
                    # Get instance details from EC2
                    instance_response = ec2_client.describe_instances(InstanceIds=[instance_id])
                    if instance_response['Reservations']:
                        instance = instance_response['Reservations'][0]['Instances'][0]
                        # Check platform details
                        if 'PlatformDetails' in instance:
                            data_dict['PlatformDetails'] = instance['PlatformDetails']  # Will be 'windows' if Windows
                        else:
                            data_dict['PlatformDetails'] = 'Unknown'  # If platform is not specified, it's Unknown
                    else:
                        data_dict['PlatformDetails'] = 'N/A'
                except Exception as e:
                    print(f"Error getting platform details for instance {instance_id}: {str(e)}")
                    data_dict['PlatformDetails'] = 'N/A'

                # Add migration effort if available
                if 'recommendationOptions' in recommendation and 'migrationEffort' in recommendation['recommendationOptions'][0] and recommendation['recommendationOptions'][0]['migrationEffort']:
                    data_dict['migrationEffort'] = recommendation['recommendationOptions'][0]['migrationEffort']
                else:
                    data_dict['migrationEffort'] = 'N/A'
                options = recommendation['recommendationOptions']
                for option in options:

                    data_dict['recommendation'] = option['instanceType']
                    if "savingsOpportunity" in option:
                        opp = option['savingsOpportunity']
                        if opp is not None and int(option['rank']) == 1:           
                            data_dict[self.ESTIMATED_SAVINGS_CAPTION] = option['savingsOpportunity']['estimatedMonthlySavings']['value']
                            break
                        else:
                            data_dict[self.ESTIMATED_SAVINGS_CAPTION] = 0.0
                    else:
                        data_dict[self.ESTIMATED_SAVINGS_CAPTION] = ''
                data_list.append(data_dict)
                data_dict={}

        df = pd.DataFrame(data_list)
        # get default temp folder to save export
        l_folder_ouput = self.appConfig.report_output_directory if self.appConfig.report_output_directory else './'

        #df.to_excel(l_folder_ouput+'/compute_optimizer.xlsx', sheet_name='EC2 Rightsizing', index=False)

        self.report_result.append({'Name':self.name(),'Data':df, 'Type':type, 'DisplayPotentialSavings':False})
        return self.report_result

    # return chart type 'chart' or 'pivot' or '' of the excel graph
    def set_chart_type_of_excel(self):
        self.chart_type_of_excel = 'pivot'
        return self.chart_type_of_excel

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # X1,Y1 to X2,Y2
        return 1, 4, 1, 4

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # X1,Y1 to X2,Y2
        return 9,1,9,-1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [ColX1, ColX2,...]
        return [9]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX1, ColX2,...]
        return [1]