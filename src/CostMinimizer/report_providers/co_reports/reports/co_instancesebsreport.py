# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ....constants import __tooling_name__

from ....report_providers.co_reports.co_base import CoBase

import pandas as pd

class CoInstancesebsreport(CoBase):

    def get_report_parameters(self) -> dict:

        #{report_name:[{'parameter_name':'value','current_value':'value','allowed_values':['val','val','val']} ]}
        return {'Ec2 Ebs Costs Details View':[{'parameter_name':'lookback_period','current_value':30,'allowed_values':['1','2','3','4','5']} ]}

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
        return 'co_instancesebsreport'

    def common_name(self) -> str:
        return 'EC2 EBS COSTS view'
    
    def service_name(self):
        return 'Compute Optimizer'
    
    def domain_name(self):
        return 'STORAGE'

    def description(self): #required - see abstract class
        return '''EC2 EBS Costs recommendations.'''
    
    def long_description(self):
        return f''' '''
    
    def _set_recommendation(self):
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing Ec2 Ebs Costs. See the report for more details.'''
    
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
        return ['account_id', 'volume_arn', 'current_volume_type', 'current_volume_size', 'root_volume', 'finding', 'number_of_recommendations', self.ESTIMATED_SAVINGS_CAPTION]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def disable_report(self) -> bool:
        return False

    def display_in_menu(self) -> bool:
        return True

    def override_column_validation(self) -> bool:
        #see description in parent class
        return True

    def get_estimated_savings(self, sum=False) -> float:
        self._set_recommendation()

        return self.set_estimate_savings(sum)

    def set_estimate_savings(self, sum=False) -> float:

        df = self.get_report_dataframe()

        if sum and (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
            return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))

        return 0.0

    def count_rows(self) -> int:
        '''Return the number of rows found in the dataframe'''
        try:
            return self.report_result[0]['Data'].shape[0] if not self.report_result[0]['Data'].empty else 0
        except Exception as e:
            self.appConfig.console.print(f"Error in counting rows: {str(e)}")
            return 0

    def calculate_savings(self):
        return self.get_estimated_savings()

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
        '''
        This function is called by the report engine to get the data for the report.

        This function returns data from the Compute Optimizer get_ebs_volume_recommendations method. 
        https://tinyurl.com/2n3mr9ju

        The estimated savings returned are the savings that are ranked #1.  
        '''

        ttype = 'chart' #other option table

        try:
            response = client.get_ebs_volume_recommendations()
        except:
            raise
        
        results_list = []
        if response and 'volumeRecommendations' in response:
            for recommendation in response['volumeRecommendations']:
                account = recommendation['accountId']
                volume_arn = recommendation['volumeArn']
                current_volume_type = recommendation['currentConfiguration']['volumeType']
                current_volume_size = recommendation['currentConfiguration']['volumeSize']
                root_volume = recommendation['currentConfiguration']['rootVolume']
                finding = recommendation['finding']

                number_of_recommendations = len(recommendation['volumeRecommendationOptions'])
                
                if number_of_recommendations == 0:
                    estimated_savings = 0.0
                elif number_of_recommendations == 1:
                    estimated_savings = recommendation['volumeRecommendationOptions'][0]['savingsOpportunity']['estimatedMonthlySavings']['value']
                elif number_of_recommendations > 1:
                    for option in recommendation['volumeRecommendationOptions']:
                        if option['rank'] == 1:
                            estimated_savings = option['savingsOpportunity']['estimatedMonthlySavings']['value']
                
                results_list.append({
                    'account_id': account,
                    'volume_arn': volume_arn,
                    'current_volume_type': current_volume_type,
                    'current_volume_size': current_volume_size,
                    'root_volume': root_volume,
                    'finding': finding,
                    'number_of_recommendations': number_of_recommendations,
                    self.ESTIMATED_SAVINGS_CAPTION: estimated_savings
                })
        else:
            results_list.append({
                'account_id': account,
                'volume_arn': '',
                'current_volume_type': '',
                'current_volume_size': '',
                'root_volume': '',
                'finding': '',
                'number_of_recommendations': 0,
                self.ESTIMATED_SAVINGS_CAPTION: ''
            })

        df = pd.DataFrame(results_list)
        self.report_result.append({'Name':self.name(),'Data':df, 'Type':ttype, 'DisplayPotentialSavings':False})

        return self.report_result

    # return chart type 'chart' or 'pivot' or '' of the excel graph
    def set_chart_type_of_excel(self):
        self.chart_type_of_excel = 'pivot'
        return self.chart_type_of_excel

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # X1,Y1 to X2,Y2
        return 10, 0, 11, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # X1,Y1 to X2,Y2
        return 17, 1, 17, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [ColX1, ColX2,...]
        return [8]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX1, ColX2,...]
        return [0,1]
    
    def require_user_provided_region(self)-> bool:
        '''
        determine if report needs to have region
        provided by user'''
        return True