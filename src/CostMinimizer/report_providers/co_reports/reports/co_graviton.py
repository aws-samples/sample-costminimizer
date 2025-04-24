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
            'instanceId', 
            'currentInstanceType', 
            'platformDetails', 
            'recommendInstanceType', 
            'finding', 
            'migrationEffort', 
            'savingsValue', 
            'monthlyCost', 
            'currency', 
            self.ESTIMATED_SAVINGS_CAPTION]

    def get_expected_column_headers(self) -> list:
        return [
            'instanceId', 
            'currentInstanceType', 
            'platformDetails', 
            'recommendInstanceType', 
            'finding', 
            'migrationEffort', 
            'savingsValue', 
            'monthlyCost', 
            'currency', 
            self.ESTIMATED_SAVINGS_CAPTION]

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
            return self.report_result[0]['Data'].shape[0]
        except Exception as e:
            self.appConfig.console.print(f"Error in counting rows: {str(e)}")
            return 0

    def calculate_savings(self):
        """Calculate potential savings from Graviton migration
        Formula: [$ EC2 total] - [$ EC2 Windows] - [$ EC2 Graviton Already] = [$EC2 Eligible Graviton]
        Then: [$ EC2 Eligible] * [%Price Delta + %Perf Delta] = $ Saving
        """
        try:
            # Default optimization factors
            price_delta = 0.20  # 20% cost reduction
            perf_delta = 0.10   # 10% performance improvement

            df = self.get_report_dataframe()

            # Calculate total EC2 spend
            total_ec2 = df['monthlyCost'].sum()

            # Filter out Windows instances and calculate their cost
            windows_cost = df[df['platformDetails'].str.contains('windows', case=False, na=False)]['monthlyCost'].sum()

            # Filter out existing Graviton instances and calculate their cost
            graviton_cost = df[df['currentInstanceType'].str.contains('g', case=False, na=False)]['monthlyCost'].sum()

            # Calculate eligible spend for Graviton migration
            eligible_spend = total_ec2 - windows_cost - graviton_cost

            # Calculate total potential savings
            total_savings = eligible_spend * (price_delta + perf_delta)

            #self.set_estimate_savings(total_savings)
            return total_savings

        except Exception as e:
            raise RuntimeError(f"Error calculating Graviton savings: {str(e)}") from e

    def sql(self, client, region, account, replace=True, query_type='sql_s_r', display = True, report_name = ''):
        type = 'chart' #other option table

        # implement object of InstanceReport class
        from ..co_base import InstanceReport

        IR = InstanceReport()

        # call do_work function of IR object
        # results is a list of dictionaries
        # each dictionary contains information about an instance
        # such as instance ID, instance type, storage size, storage cost, and monthly cost

        results = IR.get_recommendations_with_costs( (region, account), display, report_name)
        df = pd.DataFrame( results)
        self.report_result.append({'Name':self.name(),'Data':df, 'Type':type, 'DisplayPotentialSavings':True})

        return self.report_result

    # return chart type 'chart' or 'pivot' or '' of the excel graph
    def set_chart_type_of_excel(self):
        self.chart_type_of_excel = 'pivot'
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
        return [8,10]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX1, ColX2,...]
        return [2,3]