# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurSssstandardstorageoptimization(CurBase):
    """
    A class for identifying and reporting on potential cost savings by optimizing S3 standard storage usage in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify S3 buckets that could benefit from storage class transitions or lifecycle policies for cost optimization.
    """

    def name(self):
        return "cur_sssstandardstorageoptimization"

    def common_name(self):
        return "S3 Standard Storage Optimization"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'STORAGE'

    def description(self):
        return "Identifies potential cost savings from optimizing S3 standard storage usage"

    def long_description(self):
        return f'''This check analyzes S3 standard storage usage patterns in your AWS environment, helping you optimize costs and storage efficiency.
        By identifying opportunities for transitioning objects to lower-cost storage classes or implementing lifecycle policies, it enables you to make informed decisions about your S3 storage strategy.
        S3 standard storage optimization involves analyzing object access patterns, size, and age to identify objects that could be moved to more cost-effective storage classes like S3 Intelligent-Tiering, S3 Standard-IA, or S3 Glacier.
        This check helps in identifying potential savings through the implementation of lifecycle policies or the use of S3 Intelligent-Tiering for automatic cost optimization.
        Potential Savings:
        - Direct Cost Reduction: Moving infrequently accessed objects to lower-cost storage tiers can lead to immediate savings on your AWS bill.
        - Automated Cost Optimization: Implementing S3 Intelligent-Tiering or lifecycle policies can provide ongoing cost savings without manual intervention.
        - Scalable Impact: The more S3 data identified for optimization, the greater the potential savings, especially in environments with large amounts of S3 standard storage.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from optimizing S3 standard storage usage.'''

    def calculate_savings(self):
        """Calculate potential savings ."""
        try:
            if self.report_result[0]['DisplayPotentialSavings'] is False:
                return 0.0
            else:        
                query_results = self.get_query_result()
                if query_results is None or query_results.empty:
                    return 0.0

                total_savings = 0.0
                for _, row in query_results.iterrows():
                    savings = float(row[self.ESTIMATED_SAVINGS_CAPTION])
                    total_savings += savings

                self._savings = total_savings
                return total_savings
        except:
            return 0.0

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
        self.query_id = query_execution_id
        
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
        self.group_by = group_by
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
                    self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else 0.0,
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else 0.0, 
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else 0.0, 
                    self.get_required_columns()[5]: resource['Data'][5]['VarCharValue'] if 'VarCharValue' in resource['Data'][5] else 0.0
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':False})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'account_id', 
                    'bucket_name', 
                    'standard_storage_spend', 
                    'get_spend', 
                    'put_spend', 
                    'request_to_storage_spend_ratio'
                    #self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        # This method needs to be implemented with the specific SQL query for S3 standard storage optimization

        l_SQL= f"""WITH get_spend as ( 
SELECT 
line_item_resource_id as get_resource_id, 
SUM(CAST(line_item_unblended_cost AS decimal(16,8))) AS get_spend 
FROM {fqdb_name} 
WHERE 
{account_id} 
line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
AND line_item_product_code = 'AmazonS3' 
AND product_product_family != 'Data Transfer' 
AND line_item_operation in ('GetObject') 
GROUP BY 
line_item_resource_id 
), 
put_spend as ( 
SELECT 
line_item_resource_id as put_resource_id, 
SUM(CAST(line_item_unblended_cost AS decimal(16,8))) AS put_spend 
FROM {fqdb_name} 
WHERE 
{account_id} 
line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
AND line_item_product_code = 'AmazonS3' 
AND product_product_family != 'Data Transfer' 
AND line_item_operation in ('PutObject') 
GROUP BY 
line_item_resource_id 
), 
storage_spend as ( 
SELECT 
line_item_usage_account_id as account_id, 
line_item_resource_id as storage_resource_id, 
SUM(CAST(line_item_unblended_cost AS decimal(16,8))) AS standard_storage_spend 
FROM {fqdb_name} 
WHERE 
{account_id} 
line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
AND line_item_product_code = 'AmazonS3' 
AND product_product_family != 'Data Transfer' 
AND line_item_operation = 'StandardStorage' 
GROUP BY 
line_item_usage_account_id, 
line_item_resource_id 
) 
select  
account_id, 
storage_resource_id as bucket_name, 
standard_storage_spend, 
get_spend, 
put_spend, 
((get_spend + put_spend) / standard_storage_spend) as request_to_storage_spend_ratio 
from storage_spend 
LEFT JOIN get_spend ON get_resource_id = storage_resource_id 
LEFT JOIN put_spend ON put_resource_id = storage_resource_id 
WHERE  
standard_storage_spend > 100 
AND ((get_spend + put_spend) / standard_storage_spend) < .01 
ORDER BY standard_storage_spend DESC;"""
	

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

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 2, 0, 2, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 5, 1, 5, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [2,3,4,5]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [1]