# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse

class CurNatgatewayusage(CurBase):
    """
    A class for identifying and reporting on potential cost savings by optimizing NAT Gateway usage in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify NAT Gateways that may be underutilized or could be optimized for cost savings.
    """

    def name(self):
        return "cur_natgatewayusage"

    def common_name(self):
        return "NAT Gateway Usage Optimization"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'NETWORK'

    def description(self):
        return "Identifies potential cost savings from optimizing NAT Gateway usage"

    def long_description(self):
        return f'''This check analyzes NAT Gateway usage patterns in your AWS environment, helping you optimize costs and resource utilization.
        By identifying underutilized or potentially unnecessary NAT Gateways, it enables you to make informed decisions about your network architecture.
        NAT Gateway usage optimization involves analyzing metrics such as data transfer and idle time to identify gateways that may be
        underutilized or unnecessary. This check helps in right-sizing your NAT Gateway deployment and potentially consolidating traffic.
        Potential Savings:
        - Direct Cost Reduction: Removing unnecessary NAT Gateways or optimizing usage can lead to immediate savings on your AWS bill.
        - Architectural Optimization: Proper sizing and placement of NAT Gateways can improve network efficiency and reduce data transfer costs.
        - Scalable Impact: The more NAT Gateways identified for optimization, the greater the potential savings, especially in large-scale deployments.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from optimizing NAT Gateway usage.'''

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
            cur_db = self.appConfig.cur_db_arguments_parsed if (hasattr(self.appConfig, 'cur_db_arguments_parsed') and self.appConfig.cur_db_arguments_parsed is not None) else self.appConfig.config['cur_db']
            response = self.run_athena_query(client, p_SQL, self.appConfig.config['cur_s3_bucket'], cur_db)
        except Exception as e:
            l_msg = f"\n[red]Athena Query failed with state: {e} - Verify tooling CUR configuration via --configure"
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
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue']
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':False})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'resource_id', 
                    'account', 
                    'line_item_usage_type', 
                    'usage', 
                    'cost' 
                    #self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str):
        # This method needs to be implemented with the specific SQL query for NAT Gateway usage optimization

        l_SQL= f""" SELECT DISTINCT 
line_item_resource_id as resource_id, 
line_item_usage_account_id as account, 
line_item_usage_type, 
SUM(line_item_usage_amount) as "usage", 
SUM(line_item_unblended_cost) as "cost" 
FROM 
{fqdb_name} 
WHERE 
{account_id} 
AND line_item_usage_start_date >= now() - INTERVAL '3' month 
AND line_item_line_item_type = 'Usage' 
AND line_item_resource_id LIKE '%:natgateway/nat-%' 
GROUP BY 1,2,3"""

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
        return 5, 1, 5, -1

    # return range definition of the values in the excel graph
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [4]

    # return column to group by in the excel graph
    def get_group_by(self):
        # [ColX]
        return [3]