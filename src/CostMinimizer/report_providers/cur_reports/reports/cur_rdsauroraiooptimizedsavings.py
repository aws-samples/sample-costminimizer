# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurRdsauroraiooptimizedsavings(CurBase):
    """
    A class for identifying and reporting on potential cost savings by optimizing I/O operations for Amazon Aurora databases in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify Aurora databases that could benefit from I/O optimization for cost savings.
    """

    def name(self):
        return "cur_rdsauroraiooptimizedsavings"

    def common_name(self):
        return "Amazon Aurora I/O Optimization Savings"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'STORAGE'

    def description(self):
        return "Identifies potential cost savings from optimizing I/O operations for Amazon Aurora databases"

    def long_description(self):
        return f'''This check analyzes Amazon Aurora database usage patterns in your AWS environment, focusing on I/O operations.
        By identifying opportunities for I/O optimization, it enables you to make informed decisions about your database configuration and potentially reduce costs.
        Aurora I/O optimization involves analyzing metrics such as I/O operations per second (IOPS), database connections, and query patterns
        to identify areas where I/O usage can be reduced or made more efficient. This can include optimizing queries, adjusting instance types,
        or leveraging Aurora's storage auto-scaling features more effectively.
        Potential Savings:
        - Direct Cost Reduction: Optimizing I/O operations can lead to immediate savings on your AWS bill, as Aurora charges for I/O separately.
        - Performance Improvement: Efficient I/O usage can improve database performance, potentially allowing for downsizing of instances.
        - Scalable Impact: The more Aurora databases identified for I/O optimization, the greater the potential savings, especially in large-scale deployments.'''

    def author(self) -> list: 
        return ['AI Assistant']

    def report_provider(self):
        return "cur"

    def report_type(self):
        return "processed"

    def disable_report(self):
        return True

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from optimizing I/O operations for Amazon Aurora databases.'''

    def calculate_savings(self):
        """Calculate potential savings ."""
        if self.report_result[0]['DisplayPotentialSavings'] is False:
            return 0.0
        else:        
            query_results = self.get_query_result()
            if query_results is None or query_results.empty:
                return 0.0

            total_savings = 0.0
            for _, row in query_results.iterrows():
                savings = float(row['compute_total_spend'])
                total_savings += savings

            self._savings = total_savings
            return total_savings

    def count_rows(self) -> int:
        try:
            return self.report_result[0]['Data'].shape[0]
        except Exception as e:
            print(f"Error in counting rows in report_result: {str(e)}")
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
            raise Exception(l_msg)

    def addCurReport(self, client, p_SQL, range_categories, range_values, list_cols_currency, group_by, display = False, report_name = ''):
        self.graph_range_values_x1, self.graph_range_values_y1, self.graph_range_values_x2,  self.graph_range_values_y2 = range_values
        self.graph_range_categories_x1, self.graph_range_categories_y1, self.graph_range_categories_x2,  self.graph_range_categories_y2 = range_categories
        self.list_cols_currency = list_cols_currency
        self.set_chart_type_of_excel()

        try:
            cur_db = self.appConfig.cur_db_arguments_parsed if (hasattr(self.appConfig, 'cur_db_arguments_parsed') and self.appConfig.cur_db_arguments_parsed is not None) else self.appConfig.config['cur_db']
            response = self.run_athena_query(client, p_SQL, self.appConfig.config['cur_s3_bucket'], cur_db)
        except Exception as e:
            l_msg = f"Athena Query failed with state: {e} - Verify tooling CUR configuration via --configure"
            self.appConfig.console.print("\n[red]"+l_msg)
            self.logger.error(l_msg)
            return

        data_list = []

        if len(response) == 0:
            print(f"No resources found for athena request {p_SQL}.")
        else:
            if display:
                display_msg = f'[green]Running Cost & Usage Report: {report_name} / {self.appConfig.selected_regions[0]}[/green]'
            else:
                display_msg = ''
            for resource in track(response[1:], description=display_msg):
                data_dict = {
                    self.get_required_columns()[0]: resource['Data'][0]['VarCharValue'] if 'VarCharValue' in resource['Data'][0] else '',
                    self.get_required_columns()[1]: resource['Data'][1]['VarCharValue'] if 'VarCharValue' in resource['Data'][1] else '',
                    self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else '',
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else '', 
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else '', 
                    self.get_required_columns()[5]: resource['Data'][5]['VarCharValue'] if 'VarCharValue' in resource['Data'][5] else '', 
                    self.get_required_columns()[6]: resource['Data'][6]['VarCharValue'] if 'VarCharValue' in resource['Data'][6] else '', 
                    self.get_required_columns()[7]: resource['Data'][7]['VarCharValue'] if 'VarCharValue' in resource['Data'][7] else 0.0, 
                    self.get_required_columns()[8]: resource['Data'][8]['VarCharValue'] if 'VarCharValue' in resource['Data'][8] else 0.0, 
                    self.get_required_columns()[9]: resource['Data'][9]['VarCharValue'] if 'VarCharValue' in resource['Data'][9] else 0.0
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':False})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'product_code', 
                    'compute_resource_id', 
                    'storage_resource_id', 
                    'io_resource_id', 
                    'type_of_spend_1', 
                    'type_of_spend_2', 
                    'type_of_spend_3', 
                    'compute_total_spend', 
                    'storage_total_spend', 
                    'io_total_spend' 
                    #self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        # This method needs to be implemented with the specific SQL query for Amazon Aurora I/O optimization savings

        l_SQL = f"""WITH compute_spend as ( 
SELECT 
line_item_usage_account_id, 
SPLIT_PART(line_item_resource_id, ':', 7) as "line_item_resource_id", 
line_item_product_code, 
SUM(line_item_usage_amount) AS compute_usage_usage_amount, 
SUM(line_item_unblended_cost) AS compute_usage_unblended_cost, 
SUM((CASE 
WHEN ("line_item_line_item_type" = 'DiscountedUsage') THEN "reservation_effective_cost" 
WHEN ("line_item_line_item_type" = 'RIFee') THEN ("reservation_unused_amortized_upfront_fee_for_billing_period" + "reservation_unused_recurring_fee") 
WHEN (("line_item_line_item_type" = 'Fee') 
AND ("reservation_reservation_a_r_n" <> '')) THEN 0 
ELSE "line_item_unblended_cost" 
END)) "spend", 
'compute' as type_spend 
FROM {fqdb_name} , latest_date 
WHERE 
{account_id} 
line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
AND (line_item_resource_id LIKE '%cluster:cluster-%' OR line_item_resource_id LIKE '%db:%') 
AND product_database_engine IN ('Aurora MySQL','Aurora PostgreSQL') 
AND line_item_usage_amount != 0.0 
AND line_item_usage_type NOT LIKE '%InstanceUsageIOOptimized%' 
GROUP BY 
line_item_product_code, 
line_item_usage_account_id, 
line_item_resource_id 
), 
storage_spend as ( 
SELECT 
line_item_usage_account_id, 
SPLIT_PART(line_item_resource_id, ':', 7) as "line_item_resource_id", 
line_item_product_code, 
SUM(line_item_unblended_cost) AS "spend", 
'storage' as type_spend 
FROM {fqdb_name}  , latest_date 
WHERE 
{account_id} 
line_item_usage_start_date BETWEEN DATE_ADD('month', -1, {max_date}) AND {max_date} 
AND line_item_usage_amount != 0.0 
AND line_item_usage_type NOT LIKE '%IO-OptimizedStorageUsage%' 
AND line_item_usage_type LIKE '%Aurora:StorageUsage' 
GROUP BY 
line_item_product_code, 
line_item_usage_account_id, 
line_item_resource_id 
), 
io_spend as ( 
SELECT 
line_item_usage_account_id, 
SPLIT_PART(line_item_resource_id, ':', 7) as "line_item_resource_id", 
line_item_product_code, 
SUM(line_item_unblended_cost) as "spend", 
'io' as type_spend 
FROM 
{fqdb_name}  , latest_date 
WHERE 
{account_id} 
AND line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
AND line_item_usage_type LIKE '%Aurora:StorageIOUsage' 
AND line_item_line_item_type IN ('DiscountedUsage', 'Usage') 
GROUP BY 
line_item_usage_account_id, 
line_item_resource_id, 
line_item_product_code 
), 
combined_compute_and_storage as ( 
SELECT 
compute_spend.line_item_product_code as "product_code", 
compute_spend.line_item_resource_id as "compute_resource_id", 
storage_spend.line_item_resource_id as "storage_resource_id", 
compute_spend.type_spend as "type_of_spend_1", 
storage_spend.type_spend as "type_of_spend_2", 
compute_spend.spend as "compute_total_spend", 
storage_spend.spend as "storage_total_spend" 
FROM compute_spend 
LEFT JOIN storage_spend on compute_spend.line_item_resource_id = storage_spend.line_item_resource_id 
) 
SELECT 
product_code, 
compute_resource_id, 
storage_resource_id, 
io_spend.line_item_resource_id as "io_resource_id", 
type_of_spend_1, 
type_of_spend_2, 
io_spend.type_spend as "type_of_spend_3", 
compute_total_spend, 
storage_total_spend, 
io_spend.spend as "io_total_spend" 
FROM 
combined_compute_and_storage 
LEFT JOIN io_spend on combined_compute_and_storage.storage_resource_id = io_spend.line_item_resource_id;"""

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
        # Col1, Lig1 to Col2, Lig2
        return 4, 0, 6, 0

    # return range definition of the values in the excel graph
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 9, 1, 9, -1

    # return range definition of the values in the excel graph
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [7,8,9]

    # return column to group by in the excel graph
    def get_group_by(self):
        # [ColX]
        return [4,5,6]