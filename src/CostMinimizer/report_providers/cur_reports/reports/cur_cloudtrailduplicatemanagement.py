# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurCloudtrailduplicatemanagement(CurBase):
    """
    A class for identifying and reporting on duplicate CloudTrail management events in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify duplicate CloudTrail management events that may lead to unnecessary costs.
    """

    def name(self):
        return "cur_cloudtrailduplicatemanagement"

    def common_name(self):
        return "CloudTrail Duplicate Management Events"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'MANAGEMENT'

    def description(self):
        return "Identifies costs associated with duplicate CloudTrail management events"

    def long_description(self):
        return f'''This check identifies duplicate CloudTrail management events in your AWS environment, helping you optimize costs and improve efficiency.
        By pinpointing redundant event logging, it enables you to make informed decisions about your CloudTrail configuration.
        Duplicate CloudTrail management events occur when the same management event is recorded multiple times, often due to overlapping trail configurations.
        These duplicate events can lead to unnecessary storage costs and complicate log analysis.
        Potential Savings:
        - Direct Cost Reduction: Eliminating duplicate events can lead to immediate savings on CloudTrail and related storage costs.
        - Improved Log Management: Reducing duplicates simplifies log analysis and can lead to operational efficiencies.
        - Scalable Impact: The more duplicate events identified and addressed, the greater the potential savings, especially in complex, multi-account environments.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend on duplicate CloudTrail management events. The report includes trail names to help identify specific trails causing duplication.'''

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
                savings = float(row[self.ESTIMATED_SAVINGS_CAPTION])
                total_savings += savings

            self._savings = total_savings
            return total_savings

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
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else 0.0,
                    self.get_required_columns()[4]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else 0.0
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':True})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'usage_account_id',
                    'product_region_code',
                    'trail_name',
                    'cost',
                    self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def get_cloudtrail_names(self, account_id, region):
        """Get CloudTrail trail names for a specific account and region"""
        try:
            # Create a session with the specified account and region
            session = self.appConfig.auth_manager.aws_cow_account_boto_session.client.Session()
            cloudtrail_client = session.client('cloudtrail', region_name=region)
            
            # List trails in the account
            response = cloudtrail_client.list_trails()
            trails = response.get('Trails', [])
            
            # Extract trail names and return as a list
            trail_names = [trail.get('Name', 'Unknown') for trail in trails]
            return trail_names
        except Exception as e:
            self.logger.error(f"Error retrieving CloudTrail names: {str(e)}")
            return ["Unknown"]
    
    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str, current_cur_version: str, resource_id_column_exists: str):

        # generation of CUR has 2 types, legacy old and new v2.0 using dataexport.
        # The structure of Athena depends of the type of CUR
        # Also, Use may or may not include resource_if into the Athena CUR   
        if (current_cur_version == 'v2.0'):
            product_column_str_condition = "product['product_name'] = 'AWS CloudTrail'"
            product_region_code_condition = "product['region'] as product_region_code"
        else:
            product_column_str_condition = "product_product_name = 'AWS CloudTrail'"
            product_region_code_condition = "product_region_code"

        # Adjust SQL based on column existence
        if resource_id_column_exists:
            select_fields = f"line_item_usage_account_id, {product_region_code_condition}, line_item_resource_id,"
            group_by_fields = "GROUP BY 1, 2, 3 "
            trail_name_field = "COALESCE(t.line_item_resource_id, 'Unknown Trail') as trail_name"
        else:
            select_fields = f"line_item_usage_account_id, {product_region_code_condition},"
            group_by_fields = "GROUP BY 1, 2"
            trail_name_field = "'Unknown Trail' as trail_name"

        l_SQL= f"""WITH trail_data AS (
  SELECT 
    {select_fields} 
    sum(line_item_unblended_cost) as cost 
  FROM {self.cur_db}.{self.cur_table}  
  WHERE 
    {account_id} 
    line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
    AND {product_column_str_condition} 
    AND line_item_usage_type like '%PaidEventsRecorded%' 
  {group_by_fields}
) 
SELECT 
  t.line_item_usage_account_id, 
  t.product_region_code, 
  {trail_name_field}, 
  t.cost 
FROM trail_data t 
ORDER BY t.line_item_usage_account_id, t.product_region_code, t.cost DESC;"""

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
        return 3, 1, 3, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        return [3,4]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [1]