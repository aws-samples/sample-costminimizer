# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurDdbiaopt(CurBase):
    """
    A class for identifying and reporting on DynamoDB Infrequent Access (IA) optimization opportunities in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify potential cost savings by optimizing DynamoDB tables for infrequent access patterns.
    """

    def name(self):
        return "cur_ddbiaopt"

    def common_name(self):
        return "DynamoDB Infrequent Access Optimization"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'DATABASE'

    def description(self):
        return "Identifies potential cost savings from DynamoDB Infrequent Access optimization"

    def long_description(self):
        return f'''This check identifies opportunities to optimize costs in your AWS environment by leveraging DynamoDB Infrequent Access (IA) for tables with less frequent access patterns.
        By pinpointing tables that could benefit from IA, it enables you to make informed decisions about your DynamoDB configuration and potentially reduce costs.
        DynamoDB Infrequent Access (IA) is a storage class designed for tables with less frequent access patterns. 
        This check analyzes your DynamoDB usage patterns to identify tables that might benefit from switching to the IA storage class.
        Potential Savings:
        - Direct Cost Reduction: Moving eligible tables to IA can lead to immediate and substantial savings on your AWS bill.
        - Performance Optimization: By using the appropriate storage class for your access patterns, you can optimize both cost and performance.
        - Scalable Impact: The more eligible tables identified and optimized, the greater the potential savings, making this check particularly valuable for environments with extensive DynamoDB usage.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from DynamoDB Infrequent Access optimization.'''

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
            self.appConfig.logger.warning(f"Error in counting rows: {str(e)}")
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
                    self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else '',
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else '',
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else '',
                    self.get_required_columns()[5]: resource['Data'][5]['VarCharValue'] if 'VarCharValue' in resource['Data'][5] else '',
                    self.get_required_columns()[6]: resource['Data'][6]['VarCharValue'] if 'VarCharValue' in resource['Data'][6] else '',
                    self.get_required_columns()[7]: resource['Data'][7]['VarCharValue'] if 'VarCharValue' in resource['Data'][7] else '',
                    self.get_required_columns()[8]: resource['Data'][8]['VarCharValue'] if 'VarCharValue' in resource['Data'][8] else 0.0,
                    self.get_required_columns()[9]: resource['Data'][9]['VarCharValue'] if 'VarCharValue' in resource['Data'][9] else 0.0
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':True})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'usage_account_id',
                    'resource_id',
                    '_verdict',
                    '_actual_throughput_cost',
                    '_actual_storage_cost',
                    '_uses_reservations',
                    'usage_start_date',
                    'usage_end_date',
                    'potential_savings',
                    self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        # This method needs to be implemented with the specific SQL query for DynamoDB IA optimization

        l_SQL= f"""SELECT 
line_item_usage_account_id, 
line_item_resource_id, 
_verdict, 
_actual_throughput_cost, 
_actual_storage_cost, 
_uses_reservations, 
line_item_usage_start_date, 
line_item_usage_end_date, 
( 
CASE 
WHEN _verdict LIKE '%IA' THEN ( 
0.6 *(_actual_storage_cost) - 0.25 *(_actual_throughput_cost) 
) ELSE 0 
END 
) AS _potential_savings, 
( 
CASE 
WHEN _verdict LIKE '%IA' THEN ( 
0.6 *(_actual_storage_cost) - 0.25 *(_actual_throughput_cost) 
)/(round(date_diff('month',line_item_usage_start_date,line_item_usage_end_date)))  ELSE 0 
END 
) AS _potential_monthly_savings 
FROM ( 
SELECT line_item_usage_account_id,line_item_resource_id, 
( 
CASE 
WHEN _uses_reservations = 0 
AND _actual_storage_cost > 0.5 *(_actual_throughput_cost) 
THEN 'Candidate for Standard_IA' 
END 
) AS _verdict, 
_actual_throughput_cost, 
_actual_storage_cost, 
line_item_usage_start_date, 
line_item_usage_end_date, 
_uses_reservations 
FROM ( 
SELECT line_item_resource_id,line_item_usage_account_id, 
MAX( 
CASE 
WHEN "pricing_term" = 'Reserved' 
THEN 1 
ELSE 0 
END 
)   AS _uses_reservations, 
SUM( 
CASE 
WHEN line_item_usage_type LIKE '%RequestUnits' AND line_item_usage_type NOT LIKE '%IA%' THEN line_item_blended_cost 
WHEN line_item_usage_type LIKE '%CapacityUnit-Hrs' AND line_item_usage_type NOT LIKE '%IA%' THEN line_item_blended_cost ELSE 0 
END 
) AS _actual_throughput_cost, 
SUM( 
CASE 
WHEN line_item_usage_type LIKE '%TimedStorage-ByteHrs' AND line_item_usage_type NOT LIKE '%IA%' THEN line_item_blended_cost ELSE 0 
END 
) AS _actual_storage_cost, 
MIN(line_item_usage_start_date) AS line_item_usage_start_date, 
MAX(line_item_usage_end_date) AS line_item_usage_end_date 
FROM 
{fqdb_name} 
WHERE 
{account_id} 
line_item_product_code = 'AmazonDynamoDB' 
AND line_item_resource_id LIKE '%dynamodb%' 
AND line_item_resource_id NOT LIKE '%backup%' 
AND line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
GROUP BY line_item_resource_id,line_item_usage_account_id 
) 
) 
where _verdict = 'Candidate for Standard_IA' and round(date_diff('month', line_item_usage_start_date, line_item_usage_end_date)) >0 
ORDER BY _potential_savings DESC"""

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
        self.chart_type_of_excel = 'pivot'
        return self.chart_type_of_excel

    # return range definition of the categories in the excel graph,  which is the Column # in excel sheet from [0..N]
    def get_range_categories(self):
        # Col1, Lig1 to Col2, Lig2
        return 1, 0, 1, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 9, 1, 9, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        return [4,5,9,10]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [0]