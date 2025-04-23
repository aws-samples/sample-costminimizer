# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurGravitoneccsavingsrough(CurBase):
    """Cost and Usage Report based Graviton migration savings calculator."""
    
    def __init__(self, app) -> None:
        super().__init__(app)
        self._savings = 0.0
        self._recommendations = []

    def get_report_parameters(self) -> dict:
        return {}

    def set_report_parameters(self, params) -> None:
        pass

    def supports_user_tags(self) -> bool:
        return True

    def is_report_configurable(self) -> bool:
        return False

    def author(self) -> list:
        return ['slepetre']

    def name(self):
        return 'cur_gravitoneccsavingsrough'

    def common_name(self) -> str:
        return 'Graviton Savings for EC2 instances rough 30% estimation'

    def service_name(self):
        return 'Cost & Usage Report'

    def domain_name(self):
        return 'COMPUTE'

    def description(self):
        return 'Identifies potential savings from migrating to Graviton-based instances using 30% savings from current costs'

    def long_description(self) -> str:
        return '''This report analyzes your current EC2 instance usage and calculates rough potential
                 savings from migrating to equivalent Graviton-based instances. AWS Graviton 
                 processors are designed to deliver the best price performance for your cloud 
                 workloads running in Amazon EC2. It uses 30% for estimation of savings'''

    def report_type(self):
        return 'processed'

    def report_provider(self):
        return 'cur'

    def get_required_columns(self) -> list:
        return [
            'line_item_usage_account_id',
            'product_instance_type',
            'product_operating_system',
            'current_cost',
            'graviton_cost',
            'potential_savings',
            'savings'
        ]

    def get_expected_column_headers(self) -> list:
        return [
            'Account ID',
            'Instance Type',
            'OS type',
            'Current Cost',
            'Graviton Cost',
            'Potential Savings',
            'Savings %'
        ]

    def disable_report(self) -> bool:
        return True

    def _set_recommendation(self):
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend. No estimated savings recommendation is provided by this report.  Query provides account information useful for cost optimization.'''

    def count_rows(self) -> int:
        try:
            return self.report_result[0]['Data'].shape[0]
        except Exception as e:
            print(f"Error in counting rows in report_result: {str(e)}")
            return 0

    def get_estimated_savings(self, sum=True) -> float:
        """
        Calculate and return the estimated savings from addressing idle NAT Gateways.
        
        This method first sets the recommendation based on the analysis results,
        then calculates the potential savings if the identified idle NAT Gateways are addressed.
        
        Args:
            sum (bool): If True, return the total savings. If False, return savings per resource.
        
        Returns:
            float: The estimated savings in cost
        """
        self._set_recommendation()
		
        return self.set_estimate_savings(True)

    def set_estimate_savings(self, sum=False) -> float:
        """
        Calculate and return the estimated savings from addressing idle NAT Gateways.

        This method retrieves the report dataframe and calculates the total estimated savings
        if the 'sum' parameter is True. Otherwise, it returns 0.0.

        Args:
            sum (bool): If True, return the total savings. If False, return 0.0.

        Returns:
            float: The estimated savings in cost, rounded to 2 decimal places.
        """
        df = self.get_report_dataframe()

        if sum and (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
            return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))
        else:
            return 0.0

    def display_in_menu(self) -> bool:
        return True

    def calculate_savings(self):
        """Calculate potential savings from Graviton migration."""
        if self.report_result[0]['DisplayPotentialSavings'] is False:
            return 0.0
        else:
            query_results = self.get_query_result()
            if query_results is None or query_results.empty:
                return 0.0

            total_savings = 0.0
            for _, row in query_results.iterrows():
                current_cost = float(row['current_cost'])
                graviton_cost = float(row['graviton_cost'])
                savings = current_cost - graviton_cost
                total_savings += savings

            self._savings = total_savings
            return total_savings

    def get_estimated_savings(self, sum=False) -> float:
        return self._savings if sum else 0.0

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
        # insert pivot type of graphs in the excel worksheet
        self.set_chart_type_of_excel()

        try:
            cur_db = self.appConfig.cur_db_arguments_parsed if (hasattr(self.appConfig, 'cur_db_arguments_parsed') and self.appConfig.cur_db_arguments_parsed is not None) else self.appConfig.config['cur_db']
            response = self.run_athena_query(client, p_SQL, self.appConfig.config['cur_s3_bucket'], cur_db)
        except Exception as e:
            l_msg = f"Athena Query failed with state (verify Athena configuration): {e}"
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
                    self.get_required_columns()[0]: resource['Data'][0]['VarCharValue'] if 'VarCharValue' in resource['Data'][0] else '',  # line_item_usage_account_id
                    self.get_required_columns()[1]: resource['Data'][1]['VarCharValue'] if 'VarCharValue' in resource['Data'][1] else '',  # product_instance_type
                    self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else '',  # product_operating_system
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else 0.0, # current_cost
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else 0.0, # graviton_cost
                    self.get_required_columns()[5]: resource['Data'][5]['VarCharValue'] if 'VarCharValue' in resource['Data'][5] else 0.0, # potential_savings
                    self.get_required_columns()[6]: resource['Data'][6]['VarCharValue'] if 'VarCharValue' in resource['Data'][6] else 0.0  # savings
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':True})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def sql(self,fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        """Generate SQL query for Graviton migration analysis.
        Add this WHERE condition to exclude Windows OS:   AND product_operating_system NOT LIKE '%Windows%'
        """

        # This method needs to be implemented with the specific SQL query for aged EBS snapshots cost
        l_SQL = f"""WITH ec2_usage AS ( 
SELECT 
line_item_usage_account_id as account_id, 
product_instance_type as instance_type, 
product_operating_system AS os, 
SUM(line_item_unblended_cost) as current_cost, 
SUM(line_item_usage_amount) as usage_amount 
FROM 
{fqdb_name} 
WHERE 
{account_id} 
line_item_product_code = 'AmazonEC2' 
AND line_item_usage_type LIKE '%BoxUsage%' 
AND product_instance_type NOT LIKE '%.metal' 
AND product_instance_type NOT LIKE 'a1.%' 
AND product_instance_type NOT LIKE '%g.%' 
AND line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
GROUP BY 
line_item_usage_account_id, 
product_instance_type, 
product_operating_system 
) 
SELECT 
account_id as "Account ID", 
instance_type as "Instance Type", 
os AS "OS type", 
CAST(current_cost as decimal(16,2)) as "Current Cost", 
CAST(current_cost * 0.7 as decimal(16,2)) as "Graviton Cost", 
CAST(current_cost * 0.3 as decimal(16,2)) as "Potential Savings", 
CAST(30.0 as decimal(16,2)) as "Savings %" 
FROM 
ec2_usage 
WHERE 
current_cost > 0 
ORDER BY 
"Potential Savings" DESC"""

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

    # return range definition of the categories in the excel graph
    def get_range_categories(self):
        # X1,Y1 to X2,Y2
        return 2, 1, 2, -1

    # return range definition of the values in the excel graph
    def get_range_values(self):
        # X1,Y1 to X2,Y2
        return 5,1,5,-1

    # return list of columns values in the excel graph
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        # 0   account_id as "Account ID",
        # 1   instance_type as "Instance Type",
        # 2   CAST(current_cost as decimal(16,2)) as "Current Cost",
        # 3   CAST(current_cost * 0.7 as decimal(16,2)) as "Graviton Cost",
        # 4   CAST(current_cost * 0.3 as decimal(16,2)) as "Potential Savings",
        # 5   CAST(30.0 as decimal(16,2)) as "Savings %"
        return [4,5,6]

    # return column to group by in the excel graph
    def get_group_by(self):
        # [ColX]
        return [1,2]