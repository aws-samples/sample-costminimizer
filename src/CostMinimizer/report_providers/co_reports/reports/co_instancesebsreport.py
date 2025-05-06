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
        return 'COMPUTE'

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
        return ['accountId', 'region', 'instanceName', 'finding', 'recommendation', self.ESTIMATED_SAVINGS_CAPTION]


    def get_expected_column_headers(self) -> list:
        return ['accountId', 'region', 'instanceName', 'finding', 'recommendation', self.ESTIMATED_SAVINGS_CAPTION]

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

        # implement object of InstanceReport class
        from ..co_base import InstanceReport

        IR = InstanceReport()

        # call do_work function of IR object
        # results is a list of dictionaries
        # each dictionary contains information about an instance
        # such as instance ID, instance type, storage size, storage cost, and monthly cost

        results = IR.list_ebs_instances_prices( region=region, account=account, display=display, report_name=report_name)
        df = pd.DataFrame( results)
        self.report_result.append({'Name':self.name(),'Data':df, 'Type':type, 'DisplayPotentialSavings':False})

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
        return [16,17]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX1, ColX2,...]
        return [9,10]