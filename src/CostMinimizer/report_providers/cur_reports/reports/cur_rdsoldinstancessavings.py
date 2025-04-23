# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurRdsoldinstancessavings(CurBase):
    """
    A class for identifying and reporting on potential cost savings by upgrading older RDS instances in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify RDS instances that could be upgraded to newer, more cost-effective instance types.
    """

    def name(self):
        return "cur_rdsoldinstancessavings"

    def common_name(self):
        return "RDS Old Instances Upgrade Savings"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'STORAGE'

    def description(self):
        return "Identifies potential cost savings from upgrading older RDS instances"

    def long_description(self):
        return f'''This check identifies older RDS instance types in your AWS environment that could be upgraded to newer, more cost-effective alternatives.
        By pinpointing these instances, it enables you to make informed decisions about optimizing your RDS fleet for better performance and cost efficiency.
        Older RDS instance types are those that have been superseded by newer generations offering better performance, lower costs, or both.
        This check analyzes your RDS usage patterns to identify instances that could benefit from upgrading to newer instance families.
        Potential Savings:
        - Cost Reduction: Newer instance types often offer better price-performance ratios, potentially leading to significant cost savings.
        - Performance Improvement: Upgraded instances can provide better performance, potentially allowing for consolidation and further cost reduction.
        - Modernization: Keeping your RDS fleet up-to-date ensures you're leveraging the latest AWS innovations and capabilities.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from upgrading older RDS instances.'''

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
                savings = float(row['cost'])
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
                    self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else '',
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else '', 
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else '', 
                    self.get_required_columns()[5]: resource['Data'][5]['VarCharValue'] if 'VarCharValue' in resource['Data'][5] else '', 
                    self.get_required_columns()[6]: resource['Data'][6]['VarCharValue'] if 'VarCharValue' in resource['Data'][6] else '', 
                    self.get_required_columns()[7]: resource['Data'][7]['VarCharValue'] if 'VarCharValue' in resource['Data'][7] else 0.0, 
                    self.get_required_columns()[8]: resource['Data'][8]['VarCharValue'] if 'VarCharValue' in resource['Data'][8] else 0.0
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':False})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'usage_account_id', 
                    'resource_id', 
                    'product_database_engine', 
                    'product_region', 
                    'product_deployment_option', 
                    'product_instance_type', 
                    'product_instance_type_family', 
                    'unblended_rate', 
                    'cost' 
                    #self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        # This method needs to be implemented with the specific SQL query for RDS old instances upgrade savings

        l_SQL= f"""SELECT 
line_item_usage_account_id, 
SPLIT_PART(line_item_resource_id,':',7) AS split_line_item_resource_id, 
product_database_engine, 
product_region, 
product_deployment_option, 
product_instance_type, 
product_instance_type_family, 
line_item_unblended_rate, 
SUM(line_item_unblended_cost) AS cost 
 FROM 
 {fqdb_name} 
 WHERE 
{account_id} 
 product_product_name = 'Amazon Relational Database Service' 
 AND line_item_usage_type like '%InstanceUsage%' 
 AND ( 
		(line_item_usage_type not like '%t4g%') and 
		(line_item_usage_type not like '%m6g%') and 
		(line_item_usage_type not like '%m5d%') and 
		(line_item_usage_type not like '%r6g%') and 
		(line_item_usage_type not like '%r5b%') and 
		(line_item_usage_type not like '%r5d%') and 
		(line_item_usage_type not like '%x2g%') and 
		(line_item_usage_type not like '%x1e%') and 
		(line_item_usage_type not like '%z1d%') 
	) 
 AND line_item_line_item_type  IN ('Usage') 
 AND pricing_term = 'OnDemand' 
 AND line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
 GROUP BY 
  line_item_usage_account_id, 
  SPLIT_PART(line_item_resource_id,':',7), 
  line_item_unblended_rate, 
  product_database_engine, 
  product_region, 
  product_deployment_option, 
  product_instance_type, 
  product_instance_type_family 
 ORDER BY 
 cost DESC"""

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
        return 2, 0, 2, 0

    # return range definition of the values in the excel graph
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 4, 1, 4, -1

    # return range definition of the values in the excel graph
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [2,3,4]

    # return column to group by in the excel graph
    def get_group_by(self):
        # [ColX]
        return [1]