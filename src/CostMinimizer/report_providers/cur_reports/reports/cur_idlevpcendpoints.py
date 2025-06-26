# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurIdlevpcendpoints(CurBase):
    """
    A class for identifying and reporting on idle VPC endpoints in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify VPC endpoints that are not being actively used but still incurring costs.
    """

    def name(self):
        return "cur_idlevpcendpoints"

    def common_name(self):
        return "Idle VPC Endpoints"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'NETWORK'

    def description(self):
        return "Identifies idle VPC endpoints that are incurring costs"

    def long_description(self):
        return f'''This check identifies idle VPC endpoints in your AWS environment, helping you optimize costs related to network connectivity.
        By pinpointing endpoints that are not being actively used, it enables you to make informed decisions about your VPC endpoint configuration.
        VPC endpoints allow you to privately connect your VPC to supported AWS services without requiring an internet gateway, NAT device, VPN connection, or AWS Direct Connect connection.
        While VPC endpoints can improve security and reduce data transfer costs, unused endpoints still incur hourly charges.
        Potential Savings:
        - Direct Cost Reduction: Removing idle VPC endpoints can lead to immediate savings on hourly charges.
        - Resource Optimization: By focusing on active endpoints, you can ensure you're getting value from your network architecture.
        - Scalable Impact: The more idle endpoints identified and removed, the greater the potential savings, especially in large environments with multiple VPCs.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from removing idle VPC endpoints.'''

    def calculate_savings(self):
        """Calculate potential savings."""
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

    def addCurReport(self, client, p_SQL, range_categories, range_values, list_cols_currency, group_by, display = False, report_name = ''):
        self.graph_range_values_x1, self.graph_range_values_y1, self.graph_range_values_x2,  self.graph_range_values_y2 = range_values
        self.graph_range_categories_x1, self.graph_range_categories_y1, self.graph_range_categories_x2,  self.graph_range_categories_y2 = range_categories
        self.list_cols_currency = list_cols_currency
        self.group_by = group_by
        self.set_chart_type_of_excel()

        try:
            cur_db = self.appConfig.arguments_parsed.cur_db if (hasattr(self.appConfig.arguments_parsed, 'cur_db') and self.appConfig.arguments_parsed.cur_db is not None) else self.appConfig.config['cur_db']
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
                display_msg = f'[green]Running Cost & Usage Report: {report_name} / {self.appConfig.selected_regions}[/green]'
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
                    self.get_required_columns()[8]: resource['Data'][7]['VarCharValue'] if 'VarCharValue' in resource['Data'][7] else 0.0
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':True})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'account_id',
                    'line_item_resource_id',
                    'line_item_usage_type',
                    'product_region',
                    'endpoint_id',
                    'endpoint_product_code',
                    'endpoint_operation',
                    'cost',
                    self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str, current_cur_version: str, resource_id_column_exists: str):
        # generation of CUR has 2 types, legacy old and new v2.0 using dataexport.
        # The structure of Athena depends of the type of CUR
        # Also, Use may or may not include resource_if into the Athena CUR 
        
        if (current_cur_version == 'v2.0'):
            product_region_condition = "product['region']"
            line_item_product_code_condition = "product['product_name'] = 'Amazon Virtual Private Cloud'"
        else:
            product_region_condition = "product_region"
            line_item_product_code_condition = "line_item_product_code = 'AmazonVPC'"
        
        if resource_id_column_exists:
            select_fields = "line_item_usage_account_id AS account_id,\n                line_item_resource_id,"
            endpoint_id_field = "SUBSTRING(line_item_resource_id, POSITION('/' IN line_item_resource_id)+1) AS endpoint_id,"
            group_by_fields = "GROUP BY \n                line_item_usage_type, \n                line_item_line_item_type, \n                line_item_usage_account_id, \n                line_item_resource_id, \n                line_item_product_code, \n                product_region, \n                line_item_line_item_type, \n                line_item_operation \n                order by endpoint_id,line_item_usage_type"
        else:
            select_fields = "line_item_usage_account_id AS account_id,\n                'Unknown Resource' as line_item_resource_id,"
            endpoint_id_field = "'Unknown Endpoint' AS endpoint_id,"
            group_by_fields = "GROUP BY \n                line_item_usage_type, \n                line_item_line_item_type, \n                line_item_usage_account_id, \n                line_item_product_code, \n                product_region, \n                line_item_line_item_type, \n                line_item_operation \n                order by line_item_usage_type"

        l_SQL = f"""SELECT {select_fields}
line_item_usage_type, 
{product_region_condition}, 
{endpoint_id_field} 
line_item_product_code AS endpoint_product_code, 
line_item_operation AS endpoint_operation, 
ROUND(SUM(line_item_unblended_cost),2) AS cost 
FROM {self.cur_db}.{self.cur_table} 
WHERE 
{account_id} 
line_item_line_item_type LIKE 'Usage' 
AND (line_item_usage_type like '%VpcEndpoint-Bytes%' or line_item_usage_type like '%VpcEndpoint-Hours%') 
AND {line_item_product_code_condition} 
AND line_item_operation LIKE 'VpcEndpoint' 
AND line_item_usage_start_date >= now() - INTERVAL '1' month 
{group_by_fields}"""

        # Remove newlines for better compatibility with some SQL engines
        l_SQL2 = l_SQL.replace('\n', '').replace('\t', ' ')
        
        # Format the SQL query for better readability
        l_SQL3 = sqlparse.format(l_SQL2, keyword_case='upper', reindent=False, strip_comments=True)
        
        # Return the formatted query in a dictionary
        return {"query": l_SQL3}

    # return chart type 'chart' or 'pivot' or '' of the excel graph
    def set_chart_type_of_excel(self):
        self.chart_type_of_excel = 'pivot'
        return self.chart_type_of_excel

    # return range definition of the categories in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 2, 0, 2, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 7, 1, 7, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [7, 8]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [3]