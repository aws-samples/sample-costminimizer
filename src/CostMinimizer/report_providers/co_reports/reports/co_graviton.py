# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ....constants import __tooling_name__

from ..co_base import CoBase

import pandas as pd

class CoGraviton(CoBase):
    def supports_user_tags(self) -> bool:
        return True

    def is_report_configurable(self) -> bool:
        return True

    def author(self) -> list:
        return ['slepetre']

    def name(self):
        return "co_graviton"

    def common_name(self) -> str:
        return "GRAVITON view"

    def domain_name(self):
        return 'COMPUTE'

    def description(self): #required - see abstract class
        return '''Compute Optimizer recommendations for Graviton ARM64.'''

    def long_description(self):
        return f'''AWS Compute Optimizer Main View:
        This report provides an overview of AWS Compute Optimizer recommendations for your resources.
        Compute Optimizer uses machine learning to analyze your resource utilization metrics and identify optimal AWS Compute resources.
        The report includes:
        - Recommendations for EC2 instances that may be cost optimized with a migration to Graviton ARM64
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

    def service_name(self):
        return 'Compute Optimizer'

    def savings_plan_enabled(self) -> bool:
        if 'savings_plan_savings_plan_a_r_n' in self.columns:
            return True

        return False

    def reservations_enabled(self) -> bool:
        if 'reservation_reservation_a_r_n' in self.columns:
            return True

        return False

    def get_required_columns(self) -> list:
        return [
            'account_id', 
            'instance_arn', 
            'instance_name', 
            'current_instance_type', 
            'finding', 
            'number_of_recommendations', 
            'recommended_instance_type',
            self.ESTIMATED_SAVINGS_CAPTION]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def disable_report(self) -> bool:
        return False

    def display_in_menu(self) -> bool:
        return True

    def override_column_validation(self) -> bool:
        #see description in parent class
        return True

    def description(self):
        return "AWS Compute Optimizer report for Graviton optimization opportunities"

    def long_description(self):
        return """This report analyzes AWS Compute Optimizer recommendations to identify 
        potential cost savings through migration to Graviton-based instances. It considers 
        Windows workload exclusions and existing Graviton usage."""

    def get_estimated_savings(self, sum=False) -> float:
        self._set_recommendation()

        return self.set_estimate_savings(sum=sum)

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
        """Calculate potential savings from Graviton migration
        Formula: [$ EC2 total] - [$ EC2 Windows] - [$ EC2 Graviton Already] = [$EC2 Eligible Graviton]
        Then: [$ EC2 Eligible] * [%Price Delta + %Perf Delta] = $ Saving
        """
        try:
            df = self.get_report_dataframe()

            # if df is empty then return 0.0
            if df.empty:
                return 0.0
            else:
                return float(df[self.ESTIMATED_SAVINGS_CAPTION].sum())

        except Exception as e:
            raise RuntimeError(f"Error calculating Graviton savings: {str(e)}") from e

    def sql(self, client, region, account, display = True, report_name = ''):
        '''
        This function is called by the report engine to get the data for the report.

        This function returns data from the Compute Optimizer get_ec2_instance_recommendations method. 
        We filter for only recommendations with AWS_ARM64.
        https://tinyurl.com/mttmdvnb

        The estimated savings returned are the savings that are ranked #1.  
        '''

        ttype = 'chart' #other option table

        recommendationPreferences={
            'cpuVendorArchitectures': [ 'AWS_ARM64' ]
            }

        try:
            response = client.get_ec2_instance_recommendations(recommendationPreferences=recommendationPreferences)
        except:
            raise
        
        results_list = []
        if response and 'instanceRecommendations' in response:
            for recommendation in response['instanceRecommendations']:
                account = recommendation['accountId']
                instance_arn = recommendation['instanceArn']
                instance_name = recommendation['instanceName']
                current_instance_type = recommendation['currentInstanceType']
                finding = recommendation['finding']

                number_of_recommendations = len(recommendation['recommendationOptions'])

                if number_of_recommendations == 0:
                    recommended_instance_type = ''
                    estimated_savings = 0.0
                elif number_of_recommendations == 1:
                    recommended_instance_type = recommendation['recommendationOptions'][0]['instanceType']
                    estimated_savings = recommendation['recommendationOptions'][0]['savingsOpportunity']['estimatedMonthlySavings']['value']
                elif number_of_recommendations > 1:
                    for option in recommendation['recommendationOptions']:
                        if option['rank'] == 1:
                            recommended_instance_type = option['instanceType']
                            estimated_savings = option['savingsOpportunity']['estimatedMonthlySavings']['value']
                
                results_list.append({
                    'account_id': account,
                    'instance_arn': instance_arn,
                    'instance_name': instance_name,
                    'current_instance_type': current_instance_type,
                    'finding': finding,
                    'number_of_recommendations': number_of_recommendations,
                    'recommended_instance_type': recommended_instance_type,
                    self.ESTIMATED_SAVINGS_CAPTION: estimated_savings
                })
        else:
            results_list.append({
                'account_id': account,
                'instance_arn': '',
                'instance_name': '',
                'current_instance_type': '',
                'finding': '',
                'number_of_recommendations': 0,
                'recommended_instance_type': '',
                self.ESTIMATED_SAVINGS_CAPTION: ''
            })

        df = pd.DataFrame(results_list)
        self.report_result.append({'Name':self.name(),'Data':df, 'Type':ttype, 'DisplayPotentialSavings':False})

        return self.report_result

    # return chart type 'chart' or 'pivot' or '' of the excel graph
    def set_chart_type_of_excel(self):
        self.chart_type_of_excel = None
        return self.chart_type_of_excel

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 10, 1, 10, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [ColX1, ColX2,...]
        return [8]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX1, ColX2,...]
        return [1,2]
    
    def require_user_provided_region(self)-> bool:
        '''
        determine if report needs to have region
        provided by user'''
        return True