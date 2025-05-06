# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
from rich.progress import track

class CurEbsgptwotogpthree(CurBase):
    """
    A class for identifying and reporting on potential cost savings by migrating EBS volumes from gp2 to gp3 in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify EBS volumes that could benefit from migrating from gp2 to gp3 storage type.
    """

    def name(self):
        return "cur_ebsgptwotogpthree"

    def common_name(self):
        return "EBS GP2 to GP3 Migration Savings"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'STORAGE'

    def description(self):
        return "Identifies potential cost savings from migrating EBS volumes from gp2 to gp3"

    def long_description(self):
        return f'''This check identifies EBS volumes currently using gp2 storage that could benefit from migrating to gp3 in your AWS environment.
        By pinpointing these volumes, it enables you to make informed decisions about optimizing your EBS costs and performance.
        gp3 is a newer generation of general purpose EBS volume that offers better performance and lower cost compared to gp2 volumes.
        This check analyzes your EBS usage patterns to identify gp2 volumes that could be migrated to gp3 for cost savings and potentially improved performance.
        Potential Savings:
        - Direct Cost Reduction: Migrating eligible volumes from gp2 to gp3 can lead to immediate and substantial savings on your AWS bill.
        - Performance Improvement: gp3 volumes offer more consistent baseline performance and the ability to scale IOPS independently of volume size.
        - Scalable Impact: The more eligible volumes identified and migrated, the greater the potential savings, making this check particularly valuable for environments with extensive EBS usage.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing potential cost savings from migrating EBS volumes from gp2 to gp3.'''

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
                    self.get_required_columns()[5]: resource['Data'][5]['VarCharValue'] if 'VarCharValue' in resource['Data'][5] else 0, 
                    self.get_required_columns()[6]: resource['Data'][6]['VarCharValue'] if 'VarCharValue' in resource['Data'][6] else 0, 
                    self.get_required_columns()[7]: resource['Data'][7]['VarCharValue'] if 'VarCharValue' in resource['Data'][7] else 0, 
                    self.get_required_columns()[8]: resource['Data'][8]['VarCharValue'] if 'VarCharValue' in resource['Data'][8] else 0, 
                    self.get_required_columns()[9]: resource['Data'][9]['VarCharValue'] if 'VarCharValue' in resource['Data'][9] else 0,
                    self.get_required_columns()[10]: resource['Data'][10]['VarCharValue'] if 'VarCharValue' in resource['Data'][10] else 0,
                    self.get_required_columns()[11]: resource['Data'][11]['VarCharValue'] if 'VarCharValue' in resource['Data'][11] else 0.0,
                    self.get_required_columns()[12]: resource['Data'][12]['VarCharValue'] if 'VarCharValue' in resource['Data'][12] else 0.0,
                    self.get_required_columns()[13]: resource['Data'][13]['VarCharValue'] if 'VarCharValue' in resource['Data'][13] else 0.0, 
                    self.get_required_columns()[14]: resource['Data'][14]['VarCharValue'] if 'VarCharValue' in resource['Data'][14] else 0.0, 
                    self.get_required_columns()[15]: resource['Data'][15]['VarCharValue'] if 'VarCharValue' in resource['Data'][15] else 0.0, 
                    self.get_required_columns()[16]: resource['Data'][16]['VarCharValue'] if 'VarCharValue' in resource['Data'][16] else 0.0, 
                    self.get_required_columns()[17]: resource['Data'][17]['VarCharValue'] if 'VarCharValue' in resource['Data'][17] else 0.0, 
                    self.get_required_columns()[18]: resource['Data'][18]['VarCharValue'] if 'VarCharValue' in resource['Data'][18] else 0.0
                }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':False})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'billing_period', 
                    'payer_account_id', 
                    'linked_account_id', 
                    'resource_id', 
                    'volume_api_name', 
                    'storage_summary', 
                    'usage_storage_gb_mo', 
                    'usage_iops_mo', 
                    'usage_throughput_gibps_mo', 
                    'gp2_usage_added_iops_mo',
                    'gp2_usage_added_throughput_gibps_mo', 
                    'ebs_all_cost', 
                    'ebs_sc1_cost', 
                    'ebs_st1_cost', 
                    'ebs_standard_cost', 
                    'ebs_io1_cost', 
                    'ebs_io2_cost', 
                    'ebs_gp2_cost', 
                    'ebs_gp3_cost'
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        # This method needs to be implemented with the specific SQL query for EBS gp2 to gp3 migration savings
        # AND (CAST("concat"("year", '-', "month", '-01') AS date) = ("date_trunc"('month', current_date) - INTERVAL  '1' MONTH)) 

        l_SQL = f"""WITH ebs_all AS ( 
SELECT 
bill_billing_period_start_date, 
line_item_usage_start_date, 
bill_payer_account_id, 
line_item_usage_account_id, 
line_item_resource_id, 
product_volume_api_name, 
line_item_usage_type, 
pricing_unit, 
line_item_unblended_cost, 
line_item_usage_amount 
FROM 
{fqdb_name} 
WHERE 
{account_id} 
(line_item_product_code = 'AmazonEC2') 
AND (line_item_line_item_type = 'Usage') 
AND bill_payer_account_id <> '' 
AND line_item_usage_account_id <> '' 
AND line_item_usage_type LIKE '%gp%' 
AND product_volume_api_name <> '' 
AND line_item_usage_type NOT LIKE '%Snap%' 
AND line_item_usage_type LIKE '%EBS%' 
AND line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
), 
ebs_spend AS ( 
SELECT DISTINCT 
bill_billing_period_start_date AS billing_period, 
date_trunc('month',line_item_usage_start_date) AS usage_date, 
bill_payer_account_id AS payer_account_id, 
line_item_usage_account_id AS linked_account_id, 
line_item_resource_id AS resource_id, 
product_volume_api_name AS volume_api_name, 
SUM(CASE 
WHEN (((pricing_unit = 'GB-Mo' or pricing_unit = 'GB-month') or pricing_unit = 'GB-month') AND  line_item_usage_type LIKE '%EBS:VolumeUsage%') THEN line_item_usage_amount ELSE 0 
END) AS usage_storage_gb_mo, 
SUM(CASE 
WHEN (pricing_unit = 'IOPS-Mo' AND line_item_usage_type LIKE '%IOPS%') THEN line_item_usage_amount 
ELSE 0 
END) AS usage_iops_mo, 
SUM(CASE 
WHEN (pricing_unit = 'GiBps-mo' AND line_item_usage_type LIKE '%Throughput%') THEN  line_item_usage_amount 
ELSE 0 
END) AS usage_throughput_gibps_mo, 
SUM(CASE 
WHEN ((pricing_unit = 'GB-Mo' or pricing_unit = 'GB-month') AND line_item_usage_type LIKE '%EBS:VolumeUsage%') THEN (line_item_unblended_cost) 
ELSE 0 
END) AS cost_storage_gb_mo, 
SUM(CASE 
WHEN (pricing_unit = 'IOPS-Mo' AND  line_item_usage_type LIKE '%IOPS%') THEN  (line_item_unblended_cost) 
ELSE 0 
END) AS cost_iops_mo, 
SUM(CASE 
WHEN (pricing_unit = 'GiBps-mo' AND  line_item_usage_type LIKE '%Throughput%') THEN  (line_item_unblended_cost) 
ELSE 0 
END) AS cost_throughput_gibps_mo 
FROM 
ebs_all 
GROUP BY 
1, 2, 3, 4, 5, 6 
), 
ebs_spend_with_unit_cost AS ( 
SELECT 
*, 
cost_storage_gb_mo/usage_storage_gb_mo AS current_unit_cost, 
CASE 
WHEN usage_storage_gb_mo <= 150 THEN 'under 150GB-Mo' 
WHEN usage_storage_gb_mo > 150 AND usage_storage_gb_mo <= 1000 THEN 'between 150-1000GB-Mo' 
ELSE 'over 1000GB-Mo' 
END AS storage_summary, 
CASE 
WHEN volume_api_name <> 'gp2' THEN 0 
WHEN usage_storage_gb_mo*3 < 3000 THEN 3000 - 3000 
WHEN usage_storage_gb_mo*3 > 16000 THEN 16000 - 3000 
ELSE usage_storage_gb_mo*3 - 3000 
END AS gp2_usage_added_iops_mo, 
CASE 
WHEN volume_api_name <> 'gp2' THEN 0 
WHEN usage_storage_gb_mo <= 150 THEN 0 
ELSE 125 
END AS gp2_usage_added_throughput_gibps_mo, 
cost_storage_gb_mo + cost_iops_mo + cost_throughput_gibps_mo AS ebs_all_cost, 
CASE 
WHEN volume_api_name = 'sc1' THEN  (cost_iops_mo + cost_throughput_gibps_mo + cost_storage_gb_mo) 
ELSE 0 
END AS ebs_sc1_cost, 
CASE 
WHEN volume_api_name = 'st1' THEN  (cost_iops_mo + cost_throughput_gibps_mo + cost_storage_gb_mo) 
ELSE 0 
END AS ebs_st1_cost, 
CASE 
WHEN volume_api_name = 'standard' THEN  (cost_iops_mo + cost_throughput_gibps_mo + cost_storage_gb_mo) 
ELSE 0 
END AS ebs_standard_cost, 
CASE 
WHEN volume_api_name = 'io1' THEN  (cost_iops_mo + cost_throughput_gibps_mo + cost_storage_gb_mo) 
ELSE 0 
END AS ebs_io1_cost, 
CASE 
WHEN volume_api_name = 'io2' THEN  (cost_iops_mo + cost_throughput_gibps_mo + cost_storage_gb_mo) 
ELSE 0 
END AS ebs_io2_cost, 
CASE 
WHEN volume_api_name = 'gp2' THEN  (cost_iops_mo + cost_throughput_gibps_mo + cost_storage_gb_mo) 
ELSE 0 
END AS ebs_gp2_cost, 
CASE 
WHEN volume_api_name = 'gp3' THEN  (cost_iops_mo + cost_throughput_gibps_mo + cost_storage_gb_mo) 
ELSE 0 
END AS ebs_gp3_cost, 
CASE 
WHEN volume_api_name = 'gp2' THEN cost_storage_gb_mo*0.8/usage_storage_gb_mo 
ELSE 0 
END AS estimated_gp3_unit_cost 
FROM 
ebs_spend 
), 
ebs_before_map AS ( 
SELECT DISTINCT 
billing_period, 
payer_account_id, 
linked_account_id, 
resource_id, 
volume_api_name, 
storage_summary, 
SUM(usage_storage_gb_mo) AS usage_storage_gb_mo, 
SUM(usage_iops_mo) AS usage_iops_mo, 
SUM(usage_throughput_gibps_mo) AS usage_throughput_gibps_mo, 
SUM(gp2_usage_added_iops_mo) gp2_usage_added_iops_mo, 
SUM(gp2_usage_added_throughput_gibps_mo) AS gp2_usage_added_throughput_gibps_mo, 
SUM(ebs_all_cost) AS ebs_all_cost, 
SUM(ebs_sc1_cost) AS ebs_sc1_cost, 
SUM(ebs_st1_cost) AS ebs_st1_cost, 
SUM(ebs_standard_cost) AS ebs_standard_cost, 
SUM(ebs_io1_cost) AS ebs_io1_cost, 
SUM(ebs_io2_cost) AS ebs_io2_cost, 
SUM(ebs_gp2_cost) AS ebs_gp2_cost, 
SUM(ebs_gp3_cost) AS ebs_gp3_cost, 
/* Calculate cost for gp2 gp3 estimate using the following 
- Storage always 20% cheaper 
- Additional iops per iops-mo is 6% of the cost of 1 gp3 GB-mo 
- Additional throughput per gibps-mo is 50% of the cost of 1 gp3 GB-mo */ 
SUM(CASE 
WHEN volume_api_name = 'gp2' THEN ebs_gp2_cost 
- (cost_storage_gb_mo*0.8 
+ estimated_gp3_unit_cost * 0.5 * gp2_usage_added_throughput_gibps_mo 
+ estimated_gp3_unit_cost * 0.06 * gp2_usage_added_iops_mo) 
ELSE 0 
END) AS ebs_gp3_potential_savings 
FROM 
ebs_spend_with_unit_cost 
GROUP BY 
1, 2, 3, 4, 5, 6) 
SELECT DISTINCT 
* 
FROM 
ebs_before_map;"""

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
        return 4, 1, 4, 1

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 18, 1, 18, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [12,13,14,15,16,17,18,19]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [4]
