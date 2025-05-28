# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase, AWSSnapshots
import pandas as pd
import time
import sqlparse
from rich.progress import track


class CurAgedebssnapshotscost(CurBase):
    """
    A class for identifying and reporting on aged EBS snapshots costs in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify EBS snapshots that are aged and potentially leading to unnecessary costs.
    """
    def __init__(self, app) -> None:
        super().__init__(app)
        self._savings = 0.0
        self._recommendations = []

        self.snapshots = AWSSnapshots(app)

    def name(self):
        return "cur_agedebssnapshotscost"

    def common_name(self):
        return "Aged EBS Snapshots Cost"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'STORAGE'

    def description(self):
        return "Identifies costs associated with aged EBS snapshots"

    def long_description(self):
        return f'''This check identifies aged EBS snapshots in your AWS environment, helping you optimize costs and storage usage.
        By pinpointing old snapshots, it enables you to make informed decisions about your storage management.
        An aged EBS snapshot is defined as one that has been retained for an extended period, typically beyond your defined retention policy. 
        These snapshots continue to incur charges even when they may no longer be needed, leading to unnecessary costs.
        Potential Savings:
        - Direct Cost Reduction: Removing or optimizing aged EBS snapshots can lead to immediate and substantial savings on your AWS bill.
        - Storage Optimization: Regular implementation of this check can prevent the accumulation of unnecessary snapshots, leading to better storage management.
        - Scalable Impact: The more aged snapshots identified and addressed, the greater the potential savings, making this check particularly valuable for environments with extensive EBS usage.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend on aged EBS snapshots.'''

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
            l_msg = f"{response['QueryExecution']['Status']['StateChangeReason']}"
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
                # try catch block to get the snapshot info using self.snapshot
                try:
                    snapshot_id = resource['Data'][0]['VarCharValue'].split('snapshot/')[1] if 'snapshot/' in resource['Data'][0]['VarCharValue'] else ''
                    l_region = resource['Data'][1]['VarCharValue'] if 'VarCharValue' in resource['Data'][1] else ''

                    snapshot_size_info = self.snapshots.get_snapshot_info(snapshot_id, l_region)
                    if snapshot_size_info is None:
                        self.appConfig.logger.warning(f"Could not get detailed block information for snapshot {snapshot_id} in region {l_region}")
                        continue
                    volume_size_gib = snapshot_size_info.get('volume_size_gib', 0)
                    volume_size_bytes = snapshot_size_info.get('volume_size_bytes', 0)
                    start_time = snapshot_size_info.get('start_time', '')
                    description = snapshot_size_info.get('description', '')
                    state = snapshot_size_info.get('state', '')
                    actual_data_size_gib = snapshot_size_info.get('actual_data_size_gib', 0)
                
                    data_dict = {
                        self.get_required_columns_extended()[0]: resource['Data'][0]['VarCharValue'] if 'VarCharValue' in resource['Data'][0] else '',
                        self.get_required_columns_extended()[1]: l_region,
                        self.get_required_columns_extended()[2]: snapshot_id,
                        self.get_required_columns_extended()[3]: volume_size_gib,
                        self.get_required_columns_extended()[4]: volume_size_bytes,
                        self.get_required_columns_extended()[5]: start_time,
                        self.get_required_columns_extended()[6]: description,
                        self.get_required_columns_extended()[7]: state,
                        self.get_required_columns_extended()[8]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else 0,
                        self.get_required_columns_extended()[9]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else 0.0,
                        self.get_required_columns_extended()[10]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else 0.0
                    }
                except Exception as e:
                    data_dict = {
                        self.get_required_columns()[0]: resource['Data'][0]['VarCharValue'] if 'VarCharValue' in resource['Data'][0] else '',
                        self.get_required_columns()[1]: resource['Data'][1]['VarCharValue'] if 'VarCharValue' in resource['Data'][1] else '',
                        self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else 0,
                        self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else 0.0
                    }
                data_list.append(data_dict)

            df = pd.DataFrame(data_list)
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':False})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'resource_id',
                    'region',
                    'usage',
                    'cost'
                    #self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_required_columns_extended(self) -> list:
        return [
                    'resource_id',
                    'region',
                    'snapshot_id',
                    'volume_size_gib',
                    'volume_size_bytes',
                    'start_time',
                    'description',
                    'state',
                    'usage',
                    'cost',
                    self.ESTIMATED_SAVINGS_CAPTION
            ]
        
    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        # This method needs to be implemented with the specific SQL query for aged EBS snapshots cost
        # line_item_usage_start_date BETWEEN DATE_ADD('month', -1, max_date) AND max_date
        l_SQL = f"""SELECT 
DISTINCT line_item_resource_id, 
product_location as region,
SUM(line_item_usage_amount) as usage, 
SUM(line_item_unblended_cost) as cost 
FROM {fqdb_name} 
WHERE 
{account_id} 
line_item_line_item_type = 'Usage' 
AND line_item_usage_type LIKE '%EBS:SnapshotUsage' 
AND line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
GROUP BY 1, 2;"""

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
        return 2, 0, 2, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 4, 1, 4, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        return [4]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [1]

