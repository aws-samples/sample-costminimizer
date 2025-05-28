# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track
import boto3
import logging

# Add DynamoDB client class
class Dynamodb:
    def __init__(self, region, account=None):
        """Initialize DynamoDB client with region and account"""
        self.client = boto3.client('dynamodb', region_name=region)
        self.account = account
        self.region = region
    
    def describe_table(self, table_name):
        """Describe a DynamoDB table"""
        try:
            response = self.client.describe_table(TableName=table_name)
            return response
        except Exception as e:
            logging.error(f"Error describing table {table_name}: {e}")
            raise e
    
    def list_global_tables(self):
        """List global tables in the region"""
        try:
            response = self.client.list_global_tables()
            return response
        except Exception as e:
            logging.error(f"Error listing global tables: {e}")
            return {"globalTables": []}

class CurDynamodblegacyglobaltablescost(CurBase):
    """
    A class for identifying and reporting on costs associated with legacy DynamoDB global tables in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify potential cost savings by migrating from legacy to newer versions of DynamoDB global tables.
    """

    def name(self):
        return "cur_dynamodblegacyglobaltablescost"

    def common_name(self):
        return "DynamoDB Legacy Global Tables Cost"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'STORAGE'

    def description(self):
        return "Identifies costs associated with legacy DynamoDB global tables"

    def long_description(self):
        return f'''This check identifies legacy DynamoDB global tables in your AWS environment, helping you optimize costs and improve performance.
        By pinpointing legacy global tables, it enables you to make informed decisions about upgrading to newer, more cost-effective versions.
        Legacy DynamoDB global tables refer to the original version of global tables (Version 2017.11.29) which have been superseded by a newer, more efficient version (Version 2019.11.21). 
        These legacy tables may incur higher costs and have limitations compared to the newer version.
        Potential Savings:
        - Cost Reduction: Upgrading to the newer version of global tables can lead to reduced replication costs and improved efficiency.
        - Performance Improvement: The newer version offers faster replication and better conflict resolution.
        - Scalable Impact: The more legacy global tables identified and upgraded, the greater the potential savings and performance improvements.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend on legacy DynamoDB global tables.'''

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
            return self.report_result[0]['Data'].shape[0] if not self.report_result[0]['Data'].empty else 0
        except Exception as e:
            self.appConfig.logger.warning(f"Error in {self.name()}: {str(e)}")
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

    def process_check_data(self, account, region, client, result) -> list:
        """Process global tables data to identify legacy tables"""
        self.logger.info(f'Processing global tables data for account: {account} region: {region}')
        dynamodb_client = Dynamodb(region, account)
        data_list = []
        
        for global_table in result.get('globalTables', []):
            data_dict = {
                'accountId': account,
                'region': region,
                'global_table_name': global_table.get('globalTableName', '')
            }
            
            try:
                # Try to get table details to determine version
                table = dynamodb_client.describe_table(global_table.get('globalTableName', ''))
                data_dict['global_table_version'] = table.get('table', {}).get('globalTableVersion', '')
            except Exception as e:
                self.logger.info(f'Base global table not found in account: {account} region: {region}')
                data_dict['global_table_version'] = ''
            
            data_list.append(data_dict)
        
        return data_list

    def addCurReport(self, client, p_SQL, range_categories, range_values, list_cols_currency, group_by, display = False, report_name = ''):
        self.graph_range_values_x1, self.graph_range_values_y1, self.graph_range_values_x2,  self.graph_range_values_y2 = range_values
        self.graph_range_categories_x1, self.graph_range_categories_y1, self.graph_range_categories_x2,  self.graph_range_categories_y2 = range_categories
        self.list_cols_currency = list_cols_currency
        self.set_chart_type_of_excel()

        try:
            cur_db = self.appConfig.arguments_parsed.cur_db if (hasattr(self.appConfig.arguments_parsed, 'cur_db') and self.appConfig.arguments_parsed.cur_db is not None) else self.appConfig.config['cur_db']
            response = self.run_athena_query(client, p_SQL, self.appConfig.config['cur_s3_bucket'], cur_db)
        except Exception as e:
            l_msg = f"Athena Query failed with state: {e} - Verify tooling CUR configuration via --configure"
            self.appConfig.console.print("\n[red]"+l_msg)
            self.logger.error(l_msg)
            return

        cur_data_list = []

        if len(response) == 0:
            print(f"No resources found for athena request {p_SQL}.")
        else:
            if display:
                display_msg = f'[green]Running Cost & Usage Report: {report_name} / {self.appConfig.selected_regions}[/green]'
            else:
                display_msg = ''
            for resource in track(response[1:], description=display_msg):
                data_dict = {
                    self.get_required_columns()[0]: resource['Data'][0]['VarCharValue'] if 'VarCharValue' in resource['Data'][0] else '',
                    self.get_required_columns()[1]: resource['Data'][1]['VarCharValue'] if 'VarCharValue' in resource['Data'][1] else '',
                    self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else 0,
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else 0.0,
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else 0.0
                }
                cur_data_list.append(data_dict)

            # Create DataFrame from CUR data
            cur_df = pd.DataFrame(cur_data_list)

            # test if df is empty, if yes skip the rest of the function
            if not cur_df.empty:
                # Get global tables data for each region
                global_tables_data = []
                region = self.appConfig.selected_region
                try:
                    dynamodb_client = Dynamodb(region)
                    result = dynamodb_client.list_global_tables()
                    for account in cur_df['line_item_usage_account_id'].unique():
                        processed_data = self.process_check_data(account, region, None, result)
                        global_tables_data.extend(processed_data)
                except Exception as e:
                    self.logger.error(f"Error getting global tables for region {region}: {e}")
                
                # Create DataFrame from global tables data
                if global_tables_data:
                    global_tables_df = pd.DataFrame(global_tables_data)
                    
                    # Merge CUR data with global tables data
                    if not global_tables_df.empty and not cur_df.empty:
                        merged_df = pd.merge(
                            cur_df,
                            global_tables_df,
                            left_on='global_table_name',
                            right_on='global_table_name',
                            how='left'
                        )
                        
                        # Filter for legacy global tables (version 2017.11.29)
                        legacy_tables_df = merged_df[
                            (merged_df['global_table_version'] == '2017.11.29') | 
                            (merged_df['global_table_version'] == '')  # Include tables where version couldn't be determined
                        ]
                        
                        if not legacy_tables_df.empty:
                            df = legacy_tables_df
                        else:
                            df = cur_df
                    else:
                        df = cur_df
                else:
                    df = cur_df
            else:
                df = []
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':True})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'accountId',
                    'region',
                    'global_table_name',
                    'sum_usage_amount',
                    'estimated_savings',
                    self.ESTIMATED_SAVINGS_CAPTION,
                    'global_table_version'
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        # This method needs to be implemented with the specific SQL query for legacy DynamoDB global tables cost

        l_SQL = f"""SELECT 
line_item_usage_account_id, 
product_region,
SPLIT_PART(line_item_resource_id, 'table/', 2) AS global_table_name, 
SUM(CAST(line_item_usage_amount AS DOUBLE)) AS sum_line_item_usage_amount, 
SUM(CAST(line_item_blended_cost AS DECIMAL(16, 8))*.3) AS estimated_savings 
FROM {fqdb_name} 
WHERE 
{account_id} 
line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
AND line_item_product_code = 'AmazonDynamoDB' 
and line_item_usage_type like '%ReadCapacityUnit%' 
GROUP BY 
line_item_usage_account_id, 
product_region,
SPLIT_PART(line_item_resource_id, 'table/', 2)"""

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
        return 1, 0, 1, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 3, 1, 3, -1


    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        return [2,3]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [1]