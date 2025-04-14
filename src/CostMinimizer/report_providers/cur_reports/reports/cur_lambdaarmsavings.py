# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "samuel LEPETRE"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
import sys

class CurLambdaarmsavings(CurBase):
    """
    A class for identifying and reporting on potential cost savings by migrating Lambda functions to ARM-based architectures in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify Lambda functions that could benefit from migrating to ARM-based compute.
    """

    def name(self):
        return "cur_lambdaarmsavings"

    def common_name(self):
        return "Lambda ARM Migration Savings"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'COMPUTE'

    def description(self):
        return "Identifies potential cost savings from migrating Lambda functions to ARM-based architectures"

    def long_description(self):
        return f'''This check identifies Lambda functions in your AWS environment that could benefit from migrating to ARM-based compute architectures.
        By pinpointing these functions, it enables you to make informed decisions about optimizing your Lambda costs and performance.
        ARM-based Lambda functions use ARM64 architecture, which can offer better price-performance compared to x86-based functions for many workloads.
        This check analyzes your Lambda usage patterns to identify functions that could be migrated to ARM for cost savings and potentially improved performance.
        Potential Savings:
        - Direct Cost Reduction: Migrating eligible functions to ARM can lead to immediate and substantial savings on your AWS bill.
        - Performance Improvement: ARM-based functions can offer better performance for certain workloads, potentially reducing execution time and associated costs.
        - Scalable Impact: The more eligible functions identified and migrated, the greater the potential savings, making this check particularly valuable for environments with extensive Lambda usage.'''

    def author(self) -> list: 
        return ['AI Assistant']

    def report_provider(self):
        return "cur"

    def report_type(self):
        return "processed"

    def disable_report(self):
        return False

    def get_estimated_savings(self, sum=True) -> float:
        self._set_recommendation()
        return self.set_estimate_savings(True)

    def set_estimate_savings(self, sum=False) -> float:
        df = self.get_report_dataframe()

        if sum and (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
            return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))
        else:
            return 0.0

    def _set_recommendation(self):
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from migrating Lambda functions to ARM-based architectures.'''

    def calculate_savings(self):
        df = self.get_report_dataframe()
        return df

    def count_rows(self) -> int:
        try:
            return self.calculate_savings().shape[0]
        except Exception as e:
            print(f"Error in counting rows: {str(e)}")
            return 0

    def run_athena_query(self, athena_client, query, s3_results_queries, athena_database):
        try:
            response = athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={
                    'Database': athena_database
                },
                ResultConfiguration={
                    'OutputLocation': s3_results_queries
                }
            )
        except Exception as e:
            raise e

        query_execution_id = response['QueryExecutionId']
        
        while True:
            response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            state = response['QueryExecution']['Status']['State']
            
            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            
            time.sleep(1)
        
        if state == 'SUCCEEDED':
            response = athena_client.get_query_results(QueryExecutionId=query_execution_id)
            results = response['ResultSet']['Rows']
            return results
        else:
            l_msg = f"Query failed with state: {response['QueryExecution']['Status']['StateChangeReason']}"
            self.appConfig.console.print(l_msg)
            raise Exception(l_msg)

    def addCurReport(self, client, p_SQL, range_categories, range_values, list_cols_currency, group_by):
        self.graph_range_values_x1, self.graph_range_values_y1, self.graph_range_values_x2,  self.graph_range_values_y2 = range_values
        self.graph_range_categories_x1, self.graph_range_categories_y1, self.graph_range_categories_x2,  self.graph_range_categories_y2 = range_categories
        self.list_cols_currency = list_cols_currency
        self.group_by = group_by
        self.set_chart_type_of_excel()

        try:
            response = self.run_athena_query(client, p_SQL, self.appConfig.config['cur_s3_bucket'], self.appConfig.cur_db_arguments_parsed)
        except Exception as e:
            l_msg = f"\n[red]Athena Query failed with state: {e}"
            self.appConfig.console.print(l_msg)
            return

        data_list = []

        if len(response) == 0:
            print(f"No resources found for athena request {p_SQL}.")
        else:
            for resource in response[1:]:
                data_dict = {
                    self.get_required_columns()[0]: resource['Data'][0]['VarCharValue'],
                    self.get_required_columns()[1]: resource['Data'][1]['VarCharValue'],
                    self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'],
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'], 
                    self.get_required_columns()[4]: 0
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': type})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'line_item_resource_id',
                    'line_item_usage_type',
                    'usage',
                    'cost',
                    self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str):
        # This method needs to be implemented with the specific SQL query for Lambda ARM migration savings

        l_SQL = f"""WITH x86_v_arm_spend AS ( 
SELECT line_item_resource_id AS line_item_resource_id, 
bill_payer_account_id AS bill_payer_account_id, 
line_item_usage_account_id AS line_item_usage_account_id, 
line_item_line_item_type AS line_item_line_item_type, 
CASE 
SUBSTR( 
line_item_usage_type, 
(length(line_item_usage_type) - 2) 
) 
WHEN ('ARM') THEN ('arm64') 
ELSE ('x86_64') 
END AS processor, 
CASE 
SUBSTR( 
line_item_usage_type, 
(length(line_item_usage_type) - 2) 
) 
WHEN ('ARM') THEN 0 ELSE (line_item_unblended_cost * .2) 
END AS potential_savings_with_arm, 
SUM(line_item_unblended_cost) AS line_item_unblended_cost 
FROM 
{fqdb_name} 
WHERE 
{account_id} 
AND (line_item_product_code = 'AWSLambda') 
AND (line_item_operation = 'Invoke') 
AND ( 
line_item_usage_type LIKE '%Request%' 
OR line_item_usage_type LIKE '%Lambda-GB-Second%' 
) 
AND line_item_usage_start_date > CURRENT_DATE - INTERVAL '1' MONTH 
AND line_item_line_item_type IN ( 
'DiscountedUsage', 
'Usage', 
'SavingsPlanCoveredUsage' 
) 
GROUP BY 1,2,3,5,6,4) 
SELECT line_item_resource_id, 
bill_payer_account_id, 
line_item_usage_account_id, 
line_item_line_item_type, 
processor, 
sum(line_item_unblended_cost) AS line_item_unblended_cost, 
sum(potential_savings_with_arm) AS "potential_savings_with_arm" 
FROM x86_v_arm_spend 
GROUP BY 2,3,1,5,4;"""

        # Note: We use SUM(line_item_unblended_cost) to get the total cost across all usage records
        # for each unique combination of account, resource, and usage type. This gives us the
        # overall cost impact of inter-AZ traffic for each resource.

        # Remove newlines for better compatibility with some SQL engines
        l_SQL2 = l_SQL.replace('\n', '').replace('\t', ' ')
        
        # Format the SQL query for better readability:
        # - Convert keywords to uppercase for standard SQL style
        # - Remove indentation to create a compact query string
        # - Keep inline comments for maintaining explanations in the formatted query
        l_SQL3 = sqlparse.format(l_SQL2, keyword_case='upper', reindent=False, strip_comments=True)
        
        # Return the formatted query in a dictionary
        # This allows for easy extraction and potential addition of metadata in the future
        return {"query": l_SQL3}

    # return chart type 'chart' or 'pivot' or '' of the excel graph
    def set_chart_type_of_excel(self):
        self.chart_type_of_excel = ''
        return self.chart_type_of_excel

    # return range definition of the categories in the excel graph
    def get_range_categories(self):
        # Y1, X1 to X2, Y2
        return 2, 0, 2, 0

    # return range definition of the values in the excel graph
    def get_range_values(self):
        # Y1, X1 to X2, Y2
        return 4, 1, 4, -1

    # return range definition of the values in the excel graph
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [2,3,4]

    # return column to group by in the excel graph
    def get_group_by(self):
        # [ColX]
        return [1]