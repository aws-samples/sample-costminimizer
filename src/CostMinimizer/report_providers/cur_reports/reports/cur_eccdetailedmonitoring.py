# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurEccdetailedmonitoring(CurBase):
    """
    A class for identifying and reporting on potential cost savings by optimizing EC2 detailed monitoring usage in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify EC2 instances with detailed monitoring enabled that might not require such granular monitoring.
    """

    def name(self):
        return "cur_eccdetailedmonitoring"

    def common_name(self):
        return "EC2 Detailed Monitoring Optimization"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'COMPUTE'

    def description(self):
        return "Identifies potential cost savings from optimizing EC2 detailed monitoring usage"

    def long_description(self):
        return f'''This check identifies EC2 instances with detailed monitoring enabled in your AWS environment, helping you optimize costs related to CloudWatch metrics.
        By pinpointing instances that might not require such granular monitoring, it enables you to make informed decisions about your EC2 monitoring configuration.
        EC2 detailed monitoring provides metrics at 1-minute intervals, as opposed to the default 5-minute intervals with basic monitoring.
        While detailed monitoring can be beneficial for certain use cases, it comes at an additional cost and may not be necessary for all instances.
        Potential Savings:
        - Direct Cost Reduction: Disabling detailed monitoring for instances that don't require it can lead to immediate savings on CloudWatch costs.
        - Resource Optimization: By focusing detailed monitoring on critical instances, you can ensure you're getting value from the additional metrics where they matter most.
        - Scalable Impact: The more instances identified where detailed monitoring can be safely disabled, the greater the potential savings, especially in large environments.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from optimizing EC2 detailed monitoring usage.'''

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
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else 0, 
                    self.get_required_columns()[5]: resource['Data'][5]['VarCharValue'] if 'VarCharValue' in resource['Data'][5] else 0.0, 
                    self.get_required_columns()[6]: resource['Data'][6]['VarCharValue'] if 'VarCharValue' in resource['Data'][6] else 0.0, 
                    self.get_required_columns()[7]: resource['Data'][7]['VarCharValue'] if 'VarCharValue' in resource['Data'][7] else 0.0, 
                    self.get_required_columns()[8]: resource['Data'][7]['VarCharValue'] if 'VarCharValue' in resource['Data'][7] else 0.0
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':True})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'usage_account_id',
                    'InstanceId',
                    'region',
                    'resource_id', 
                    'usage_quantity', 
                    'usage_cost', 
                    'rate', 
                    'savings',
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
            line_item_product_code_condition = "product['product_name'] = 'Amazon Elastic Compute Cloud'"
            product_product_name_condition = "product['product_name'] = 'AmazonCloudWatch'"
        else:
            product_region_condition = "product_region"
            line_item_product_code_condition = "line_item_product_code = 'AmazonEC2'"
            product_product_name_condition = "product_product_name = 'AmazonCloudWatch'"
        
        # Adjust SQL based on column existence
        if resource_id_column_exists:
            resource_select = "line_item_resource_id"
            resource_group = "line_item_resource_id"
            line_item_product_code_condition = line_item_product_code_condition + " and line_item_resource_id like '%i%' "
            resource_where = "split_part(split_part(m.line_item_resource_id,':',6),'/',2)=b.line_item_resource_id"
            resource_split = f"""split_part(split_part(m.line_item_resource_id,':',6),'/',2) AS InstanceId, 
split_part(m.line_item_resource_id,':',4) region, 
m.line_item_resource_id"""
        else:
            resource_select = "'Unknown Resource' as line_item_resource_id"
            resource_group = "'Unknown Resource'"
            resource_where = "1=1"  # Always true condition since we can't filter by resource
            resource_split = f"""'Unknown Instance' as InstanceId, 
{product_region_condition} as region, 
'Unknown Resource' as line_item_resource_id"""

        l_SQL= f"""WITH base as 
(select {resource_select} 
FROM {self.cur_db}.{self.cur_table} 
WHERE 
{account_id} 
line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
AND {line_item_product_code_condition} 
AND line_item_usage_type LIKE '%BoxUsage%' 
group by {resource_group} 
having sum(line_item_usage_amount)>168 
ORDER BY 1) 
SELECT 
m.line_item_usage_account_id, 
{resource_split}, 
sum(m.line_item_usage_amount) AS usage_quantity, 
sum(m.line_item_unblended_cost) AS usage_cost, 
sum(m.line_item_unblended_cost)/sum(m.line_item_usage_amount) AS rate, 
(sum(m.line_item_unblended_cost)/sum(m.line_item_usage_amount))*7 AS savings 
FROM 
{self.cur_db}.{self.cur_table} m, base b 
WHERE 
{account_id} 
{resource_where} 
AND m.line_item_usage_start_date BETWEEN DATE_ADD('day', -2, DATE('{max_date}')) AND DATE('{max_date}') 
AND {product_product_name_condition} AND m.line_item_usage_type LIKE '%%MetricMonitorUsage%%' AND m.line_item_operation='MetricStorage:AWS/EC2' 
AND m.line_item_line_item_type ='Usage' 
group by m.line_item_usage_account_id,
m.{resource_group},  
split_part(split_part(m.line_item_resource_id,':',6),'/',2),split_part(m.line_item_resource_id,':',4), 
{product_region_condition} 
order by 1,2"""

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
        self.chart_type_of_excel = 'pivot'
        return self.chart_type_of_excel

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 2, 0, 2, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 8, 1, 8, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [6,7,8,9]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [2]