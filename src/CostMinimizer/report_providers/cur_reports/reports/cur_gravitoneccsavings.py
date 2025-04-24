# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase, AWSPricing, InstanceConversionToGraviton
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurGravitoneccsavings(CurBase):
    """Cost and Usage Report based Graviton migration savings calculator."""
    
    def __init__(self, app) -> None:
        super().__init__(app)
        self._savings = 0.0
        self._recommendations = []

        self.conversion = InstanceConversionToGraviton( self.appConfig)
        self.pricing = AWSPricing(app)

        self.graviton_ratio_performance = .15  # Additional 10% ration price performance for graviton

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
        return 'cur_gravitoneccsavings'

    def common_name(self) -> str:
        return 'Graviton Savings for EC2 instances'

    def service_name(self):
        return 'Cost & Usage Report'

    def domain_name(self):
        return 'COMPUTE'

    def description(self):
        return 'Identifies potential savings from migrating to Graviton-based instances'

    def long_description(self) -> str:
        return '''This report analyzes your current EC2 instance usage and calculates potential
                 savings from migrating to equivalent Graviton-based instances. AWS Graviton 
                 processors are designed to deliver the best price performance for your cloud 
                 workloads running in Amazon EC2.'''

    def report_type(self):
        return 'processed'

    def report_provider(self):
        return 'cur'

    def get_required_columns(self) -> list:
        return [
            'usage_account_id',
            'product_instance_type',
            'graviton_instance_type',
            'product_operating_system',
            'availability_zone',
            'product_tenancy',
            'product_region',
            'current_instance_unit_cost',
            'graviton_instance_unit_cost',
            'current_cost',
            'amortized_cost',
            self.ESTIMATED_SAVINGS_CAPTION,
            'savings_%'
        ]

    def get_expected_column_headers(self) -> list:
        return [
            'Account ID',
            'Current Instance Type',
            'Graviton Instance Type',
            'OS Type',
            'AZ',
            'Tenancy',
            'Region',
            'Current Instance Unit Cost',
            'Graviton Instance Unit Cost',
            'Current Cost',
            'Amortized Cost',
            'Potential Savings',
            'Savings %'
        ]
    
    def disable_report(self) -> bool:
        return False

    def display_in_menu(self) -> bool:
        return True

    def count_rows(self) -> int:
        try:
            return self.report_result[0]['Data'].shape[0]
        except Exception as e:
            print(f"Error in counting rows in report_result: {str(e)}")
            return 0

    def _set_recommendation(self):
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend. The estimated savings are the difference between the cost of actual running instances and they were migrated to graviton but using ON DEMAND pricing.'''

    def get_estimated_savings(self, sum=True) -> float:
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
                potential_savings = float(row[self.ESTIMATED_SAVINGS_CAPTION])

                total_savings += potential_savings

            self._savings = total_savings
            return total_savings

    def get_estimated_savings(self, sum=True) -> float:
        self._set_recommendation()
        return self.set_estimate_savings(True)

    def set_estimate_savings(self, sum=False) -> float:
        df = self.get_report_dataframe()

        if sum and (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
            return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))
        else:
            return 0.0

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

                current_cost = float(resource['Data'][6]['VarCharValue'])
                region = 'us-east-1'
                accountid = resource['Data'][0]['VarCharValue']
                instance_type = resource['Data'][1]['VarCharValue']
                family = resource['Data'][1]['VarCharValue'].split('.')[0]
                l_region = self.conversion.get_region_name(resource['Data'][5]['VarCharValue'] )
                l_operating_system = resource['Data'][2]['VarCharValue'] 
                l_tenancy = resource['Data'][4]['VarCharValue'] 
                l_pre_installed_software = ''
                graviton_unit_price = -1
                value_graviton_unit_price = -1
                value_current_unit_price = -1

                # Try to use the AWS API request to compute the equivalence instance type in terms of graviton instance, and also the graviton instance unit cost
                try:
                    graviton_equiv = self.conversion.get_graviton_equivalent(family)

                    current_unit_price = self.pricing.get_instance_price(instance_type, l_region, l_operating_system, l_tenancy, l_pre_installed_software)
                    graviton_unit_price = self.pricing.get_instance_price(graviton_equiv+'.'+instance_type.split('.')[1])

                    value_graviton_unit_price = float(graviton_unit_price['on_demand']['price_per_hour'])
                    value_current_unit_price = float(current_unit_price['on_demand']['price_per_hour'])

                except:
                    # Unable to access the AWS API requests to get the unit costs of instances, probably due to permissions, then
                    #  try to use the tables in costminimizer sqlite3 database to compute the equivalence instance type in terms of graviton instance, and also the graviton instance unit cost
                    graviton_equiv = self.conversion.get_graviton_equivalent_from_db(family)
                    if graviton_equiv != '':
                        value_current_unit_price = self.pricing.get_ec2instance_price_from_db(
                            instance_type, 
                            l_region, 
                            l_operating_system, 
                            l_tenancy, 
                            l_pre_installed_software)
                        value_graviton_unit_price = self.pricing.get_ec2instance_price_from_db(
                            graviton_equiv+'.'+instance_type.split('.')[1], 
                            l_region, 
                            l_operating_system, 
                            l_tenancy, 
                            l_pre_installed_software)

                    # unit_price force to 0 if OS is Windows, except if tagging is set to force it like dotnetcore_onwindows
                    if ("Windows" in l_operating_system):
                        if (self.TAG_KEY.strip() != ''):
                            try:
                                l_tag_value = instance_type = resource['Data'][-1]['VarCharValue']
                                if (self.TAG_VALUE_FILTER not in l_tag_value):
                                    value_graviton_unit_price = 0
                                else:
                                    value_graviton_unit_price = self.pricing.get_ec2instance_price_from_db(
                                        graviton_equiv+'.'+instance_type.split('.')[1], 
                                        l_region, 
                                        "LinuxNA", 
                                        l_tenancy, 
                                        l_pre_installed_software)                                    
                            except:
                                value_graviton_unit_price = 0
                        else:
                            value_graviton_unit_price = 0

                # only if prices are returned for current instance and graviton instance
                if value_current_unit_price > 0 and value_graviton_unit_price > 0:
                    ratio = value_graviton_unit_price / value_current_unit_price / (1 + self.graviton_ratio_performance)
                else:
                    ratio = 1
                savings = current_cost - (current_cost * ratio)

                data_dict = {
                    self.get_required_columns()[0]: resource['Data'][0]['VarCharValue'] if 'VarCharValue' in resource['Data'][0] else '',   # line_item_usage_account_id
                    self.get_required_columns()[1]: resource['Data'][1]['VarCharValue'] if 'VarCharValue' in resource['Data'][1] else '',   # product_instance_type
                    self.get_required_columns()[2]: graviton_equiv,                                                                         # graviton_instance_type
                    self.get_required_columns()[3]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else '',   # product_operating_system
                    self.get_required_columns()[4]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else '',   # line_item_availability_zone
                    self.get_required_columns()[5]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else '',   # product_tenancy
                    self.get_required_columns()[6]: resource['Data'][5]['VarCharValue'] if 'VarCharValue' in resource['Data'][5] else '',   # product_region
                    self.get_required_columns()[7]: value_current_unit_price,                                                               # current_instance_unit_cost
                    self.get_required_columns()[8]: value_graviton_unit_price,                                                              # graviton_instance_unit_cost
                    self.get_required_columns()[9]: current_cost,                                                                           # current_cost
                    self.get_required_columns()[10]: resource['Data'][7]['VarCharValue'] if 'VarCharValue' in resource['Data'][7] else 0.0, # amortized_cost
                    self.get_required_columns()[11]: savings,                                                                               # potential_savings
                    self.get_required_columns()[12]: (1-ratio)                                                                              # ration %
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':True})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def sql(self,fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        """Generate SQL query for Graviton migration analysis.
        Add this WHERE condition to exclude Windows OS:   AND product_operating_system NOT LIKE '%Windows%'
        """

        if len(self.TAG_KEY) > 0:
            l_SQL_tag = f' AND {self.TAG_KEY} LIKE {self.TAG_VALUE_FILTER} '
            l_SQL_tag_groupby = f' ,{self.TAG_KEY} '
        else:
            l_SQL_tag = ''
            l_SQL_tag_groupby = ''

        # This method needs to be implemented with the specific SQL query for aged EBS snapshots cost
        # optional : line_item_resource_id as Resource_id,
        l_SQL = f"""WITH ec2_usage AS ( 
SELECT 
line_item_usage_account_id as account_id, 
product_instance_type as instance_type, 
product_operating_system AS os, 
line_item_availability_zone AS az, 
product_tenancy as tenancy, 
product_region as region, 
SUM(line_item_unblended_cost) as current_cost, 
SUM(CASE 
WHEN line_item_line_item_type = 'SavingsPlanCoveredUsage' THEN savings_plan_savings_plan_effective_cost 
WHEN line_item_line_item_type = 'DiscountedUsage' THEN reservation_effective_cost 
ELSE line_item_unblended_cost 
END) AS amortized_cost, 
SUM(line_item_usage_amount) as usage_amount 
{l_SQL_tag_groupby} 
FROM 
{fqdb_name} 
WHERE 
{account_id} 
line_item_product_code = 'AmazonEC2' 
AND line_item_usage_type LIKE '%BoxUsage%' 
AND line_item_line_item_type IN ('Usage', 'DiscountedUsage', 'SavingsPlanCoveredUsage') 
AND product_instance_type NOT LIKE '%.metal' 
AND product_instance_type NOT LIKE 'a1.%' 
AND product_instance_type NOT LIKE '%g.%' 
AND line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
GROUP BY 
line_item_usage_account_id, 
product_instance_type, 
product_operating_system, 
line_item_availability_zone, 
product_tenancy, 
product_region 
{l_SQL_tag_groupby} 
) 
SELECT 
account_id as Account_ID, 
instance_type as Instance_Type, 
os AS OS_type, 
az AS AZ, 
tenancy as Tenancy, 
region as Region, 
CAST(current_cost as decimal(16,2)) as Current_Cost, 
CAST(amortized_cost as decimal(16,2)) as Amortized_Cost, 
CAST(0 as decimal(16,2)) as USage_Amount 
{l_SQL_tag_groupby} 
FROM 
ec2_usage 
WHERE 
current_cost > 0"""

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
        # X1,Y1 to X2,Y2
        return 1, 1, 2, -1

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # X1,Y1 to X2,Y2
        return 11,1,11,-1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        # 0   account_id as "Account ID",
        # 1   instance_type as "Instance Type",
        # 2   CAST(current_cost as decimal(16,2)) as "Current Cost",
        # 3   CAST(current_cost * 0.7 as decimal(16,2)) as "Graviton Cost",
        # 4   CAST(current_cost * 0.3 as decimal(16,2)) as "Potential Savings",
        # 5   CAST(30.0 as decimal(16,2)) as "Savings %"
        return [7,8,9,10,11]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [2,1]