# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase, AWSPricing, InstanceConversionToGraviton
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurGravitonlambdasavings(CurBase):
    """
    A class for identifying and reporting on potential cost savings by migrating Lambda functions to ARM-based architectures in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify Lambda functions that could benefit from migrating to ARM-based compute.
    """
    def __init__(self, app) -> None:
        super().__init__(app)
        self._savings = 0.0
        self._recommendations = []

        self.conversion = InstanceConversionToGraviton( self.appConfig)
        self.pricing = AWSPricing(app)

        self.graviton_ratio_performance = .15  # Additional 10% ration price performance for graviton

    def name(self):
        return "cur_gravitonlambdasavings"

    def common_name(self):
        return "Graviton Savings for Lambda resources"

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
        try:
            if sum and (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
                return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))
            else:
                return 0.0
        except:
            return 0.0

    def _set_recommendation(self):
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from migrating Lambda functions to ARM-based architectures.'''

    def calculate_savings(self):
        """Calculate potential savings from LAMBDA Graviton migration."""
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

                current_cost = float(resource['Data'][7]['VarCharValue'])
                l_region = self.conversion.get_region_name(resource['Data'][6]['VarCharValue'] )
                l_usage_type = resource['Data'][4]['VarCharValue'] 
                l_processor = resource['Data'][5]['VarCharValue'] 
                graviton_unit_price = -1
                value_graviton_unit_price = -1
                value_current_unit_price = -1

                # Try to use the AWS API request to compute the equivalence instance type in terms of graviton instance, and also the graviton instance unit cost
                try:
                    if (l_processor == 'x86'):
                        current_unit_price = self.pricing.get_lambda_price(
                            l_region, 
                            l_usage_type)
                        graviton_unit_price = self.pricing.get_lambda_price(
                            l_region, 
                            l_usage_type+'-ARM')

                        value_graviton_unit_price = float(graviton_unit_price['on_demand']['price_per_hour'])
                        value_current_unit_price = float(current_unit_price['on_demand']['price_per_hour'])
                    else:
                        value_graviton_unit_price = 0
                        value_current_unit_price = 0
                except:
                    # Unable to access the AWS API requests to get the unit costs of instances, probably due to permissions, then
                    #  try to use the tables in costminimizer sqlite3 database to compute the equivalence instance type in terms of graviton instance, and also the graviton instance unit cost
                    if (l_processor == 'x86'):
                        value_current_unit_price = self.pricing.get_lambda_price_from_db(
                            l_region, 
                            l_usage_type)
                        value_graviton_unit_price = self.pricing.get_lambda_price_from_db(
                            l_region, 
                            l_usage_type+'-ARM')
                    else:
                        value_graviton_unit_price = 0
                        value_current_unit_price = 0

                # only if prices are returned for current instance and graviton instance
                if value_current_unit_price > 0 and value_graviton_unit_price > 0:
                    ratio = (value_graviton_unit_price / value_current_unit_price) / (1 + self.graviton_ratio_performance)
                else:
                    ratio = 1
                savings = current_cost - (current_cost * ratio)

                data_dict = {
                    self.get_required_columns()[0]: resource['Data'][0]['VarCharValue'] if 'VarCharValue' in resource['Data'][0] else '',   # line_item_resource_id
                    self.get_required_columns()[1]: resource['Data'][1]['VarCharValue'] if 'VarCharValue' in resource['Data'][1] else '',   # bill_payer_account_id
                    self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else '',   # line_item_usage_account_id
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else '',   # line_item_line_item_type
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else '',   # line_item_usage_type
                    self.get_required_columns()[5]: resource['Data'][5]['VarCharValue'] if 'VarCharValue' in resource['Data'][5] else '',   # processor
                    self.get_required_columns()[6]: resource['Data'][6]['VarCharValue'] if 'VarCharValue' in resource['Data'][6] else '',   # product_region'
                    self.get_required_columns()[7]: resource['Data'][7]['VarCharValue'] if 'VarCharValue' in resource['Data'][7] else 0.0,  # line_item_unblended_cost
                    self.get_required_columns()[8]: resource['Data'][8]['VarCharValue'] if 'VarCharValue' in resource['Data'][8] else 0.0,  # potential_savings_with_arm_rough20percent
                    self.get_required_columns()[9]: value_current_unit_price,              # current_instance_unit_cost
                    self.get_required_columns()[10]: value_graviton_unit_price,             # graviton_instance_unit_cost
                    self.get_required_columns()[11]: current_cost,                          # current_cost
                    self.get_required_columns()[12]: savings,                              # potential_savings
                    self.get_required_columns()[13]: (1-ratio)                             # ration %
                }
                data_list.append(data_dict)

                
            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':True})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'resource_id',
                    'bill_payer_account_id',
                    'usage_account_id',
                    'line_item_type',
                    'usage_type',
                    'processor',
                    'product_region',
                    'unblended_cost',
                    "potential_savings_with_arm_rough20percent",
                    'current_instance_unit_cost',
                    'graviton_instance_unit_cost',
                    'current_cost',
                    'potential_savings',
                    self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return [
                    'resource_id',
                    'bill_payer_account_id',
                    'usage_account_id',
                    'line_item_type',
                    'usage_type',
                    'processor',
                    'product_region',
                    'unblended_cost',
                    "potential_savings_with_arm_rough20percent",
                    'Current Instance Unit Cost',
                    'Graviton Instance Unit Cost',
                    'Current Cost',
                    'Potential Savings',
                    self.ESTIMATED_SAVINGS_CAPTION
            ]

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        # This method needs to be implemented with the specific SQL query for Lambda ARM migration savings

        l_SQL = f"""WITH x86_v_arm_spend AS ( 
SELECT line_item_resource_id AS line_item_resource_id, 
bill_payer_account_id AS bill_payer_account_id, 
line_item_usage_account_id AS line_item_usage_account_id, 
line_item_line_item_type AS line_item_line_item_type, 
line_item_usage_type,
CASE 
WHEN SUBSTR( 
line_item_usage_type, 
(length(line_item_usage_type) - 4) 
) = '-ARM' 
THEN ('ARM') 
ELSE ('x86') 
END AS processor, 
product_region,
CASE SUBSTR( line_item_usage_type, (length(line_item_usage_type) - 2) ) 
WHEN ('ARM') THEN 0 ELSE (line_item_unblended_cost * .2) 
END AS savings_with_arm, 
SUM(line_item_unblended_cost) AS line_item_unblended_cost 
FROM 
{fqdb_name} 
WHERE 
{account_id} 
(line_item_product_code = 'AWSLambda') 
AND (line_item_operation = 'Invoke') 
AND ( 
line_item_usage_type LIKE '%Request%' 
OR line_item_usage_type LIKE '%Lambda-GB-Second%' 
) 
AND line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
AND line_item_line_item_type IN ( 
'DiscountedUsage', 
'Usage', 
'SavingsPlanCoveredUsage' 
) 
GROUP BY 1,2,3,4,5,6,7,8) 
SELECT line_item_resource_id, 
bill_payer_account_id, 
line_item_usage_account_id, 
line_item_line_item_type, 
line_item_usage_type,
processor, 
product_region, 
sum(line_item_unblended_cost) AS line_item_unblended_cost, 
sum(savings_with_arm) AS potential_savings_with_arm_rough20percent 
FROM x86_v_arm_spend 
GROUP BY 1,2,3,4,5,6,7;"""

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
        # Y1, X1 to Y2, X2
        return 4, 0, 5, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Y1, X1 to Y2, X2
        return 13, 1, 13, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [7,8,9,10,11,12,13]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [4,5]