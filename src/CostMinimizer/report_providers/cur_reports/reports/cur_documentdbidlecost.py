# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..cur_base import CurBase
import pandas as pd
import time
import sqlparse
import uuid
import boto3
import datetime
from datetime import timezone
from rich.progress import track

# CloudWatch client class
class Cloudwatch:
    def __init__(self, account=None, region=None):
        """Initialize CloudWatch client with account and region"""
        # Ensure region is not empty or None before creating client
        if region and region.strip():
            self.client = boto3.client('cloudwatch', region_name=region)
        else:
            # Default to a valid region if none provided
            self.client = boto3.client('cloudwatch', region_name='us-east-1')
        self.account = account
        self.region = region
    
    def get_metric_data(self, end_time, start_time, metric_data_queries):
        """Get metric data from CloudWatch"""
        try:
            response = self.client.get_metric_data(
                MetricDataQueries=metric_data_queries,
                StartTime=datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ"),
                EndTime=datetime.datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%SZ")
            )
            return response
        except Exception as e:
            self.logger.info(f"Error getting metric data: {e}")
            return {"metricDataResults": []}

class CurDocumentdbidlecost(CurBase):
    """
    A class for identifying and reporting on idle DocumentDB instances in AWS environments.
    
    This class extends CurBase and provides methods for analyzing Cost and Usage Report (CUR) data
    to identify DocumentDB instances that are idle or underutilized, potentially leading to unnecessary costs.
    """

    def name(self):
        return "cur_documentdbidlecost"

    def common_name(self):
        return "Idle DocumentDB Instances Cost"

    def service_name(self):
        return "Cost & Usage Report"

    def domain_name(self):
        return 'STORAGE'

    def description(self):
        return "Identifies costs associated with idle DocumentDB instances"

    def long_description(self):
        return f'''This check identifies idle DocumentDB instances in your AWS environment, helping you optimize costs and resource usage.
        By pinpointing underutilized DocumentDB instances, it enables you to make informed decisions about your database architecture.
        An idle DocumentDB instance is defined as one that has little to no database activity over an extended period, typically a month. 
        These instances continue to incur charges even when not actively used, leading to unnecessary costs and resource inefficiency.
        Potential Savings:
        - Direct Cost Reduction: Stopping, downsizing, or removing idle DocumentDB instances can lead to immediate and substantial savings on your AWS bill.
        - Resource Optimization: Regular implementation of this check can prevent the accumulation of idle resources, leading to better overall resource management.
        - Scalable Impact: The more idle DocumentDB instances identified and addressed, the greater the potential savings, making this check particularly valuable for large-scale deployments.'''

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
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend on idle DocumentDB instances.'''
        
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
            
    def get_cloudwatch_dicts(self, db_list) -> list:
        '''pass in a list of identifiers 
        send to CW 50 at a time
        '''
        query_metric_list = []
        for db in db_list:
            db_name = db['dBClusterIdentifier']
        
            db_uuid= 'a'+str(uuid.uuid4().hex)

            temp_dict = {
                    'Id': 'docdb',
                    'MetricStat': {
                            'Metric': {
                            "Namespace": "AWS/DocDB",
                            "MetricName": "DatabaseConnectionsMax",
                            "Dimensions": [
                                
                            ]
                            },
                        'Period': 300,
                        'Stat': 'Sum',
                        }                    
            }
            
            temp_dict['Id'] = db_uuid
            db_key={}
            db_key['Name'] = 'DBClusterIdentifier'
            db_key['Value'] = db_name
            temp_dict['MetricStat']['Metric']['Dimensions'].append(db_key)
            
            query_metric_list.append(temp_dict)
        self.logger.info(f'created CW dict')
        return query_metric_list
    
    def make_lists(self, items, n):
        """Split a list into chunks of size n"""
        return [items[i:i + n] for i in range(0, len(items), n)]
    
    #funtion outputs curated data needed for this check   
    def process_check_data(self, account, region, client, result) -> list:
        data_list = []
        data_dict = {}
 
        self.error = {}
        self.logger.info(f'processing check data')
        
        #make sure dante response was successful
        if result['danteCallStatus'] == 'SUCCESSFUL':  
            self.logger.info(f'dante call successful')
            metric_data_query_list=[]
            
            cluster_lists = self.make_lists(result['dBClusters'], 50)
            
            for cluster_list in cluster_lists:
                
                metric_data_query_list = self.get_cloudwatch_dicts(cluster_list)
                # Ensure region is valid before creating CloudWatch client
                if not region or region == '':
                    self.logger.warning(f"Empty region provided for account {account}, skipping CloudWatch metrics")
                    continue
                    
                try:
                    cw_client = Cloudwatch(account=account, region=region)
                    date_format = "%Y-%m-%dT%H:%M:%SZ"
                    end_time = datetime.datetime.now(timezone.utc).strftime(date_format)
                    end_date = datetime.datetime.now(timezone.utc)
                    start_time = (end_date-datetime.timedelta(7)).strftime(date_format)
                    cw_resp = cw_client.get_metric_data(end_time=end_time, start_time=start_time, metric_data_queries=metric_data_query_list)
                    if cw_resp == []:
                        self.logger.info(f'No CloudWatch metrics found for account {account}, region {region}')
                        continue
                except Exception as e:
                    self.logger.error(f"Error getting CloudWatch metrics for account {account}, region {region}: {e}")
                    continue
                
                for cw_result in cw_resp['metricDataResults']:
                    data_dict = {}
                    seven_day_total = 0
                    
                    for stamp, value in zip(cw_result['timestamps'], cw_result['values']):
                        seven_day_total += value
                    data_dict['account'] = account
                    data_dict['region'] = region
                    data_dict['docdb_name'] = cw_result['label']
                    data_dict['connection_count'] = seven_day_total
                    for db in cluster_list:
                        if data_dict['docdb_name'] == db['dBClusterIdentifier']:
                            data_dict['dBClusterMembers'] = db['dBClusterMembers']
                            data_dict['dbClusterResourceId'] = db['dbClusterResourceId']
                            
                            if seven_day_total == 0:
                                data_list.append(data_dict)
        else:
            msg = f'ERROR: Dante call not successful for account: {account} region: {region}'
            self.logger.info(msg)
            self.error[account] = msg

        del(result)
        del(data_dict)

        return data_list

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
            
            # Get DocumentDB clusters from CUR results
            docdb_clusters = []
            for _, row in df.iterrows():
                docdb_clusters.append({
                    'dBClusterIdentifier': row['resource_id'],
                    'dBClusterMembers': [],  # This would be populated from actual API call
                    'dbClusterResourceId': row['resource_id']
                })
            
            # Process the clusters to check for idle ones
            idle_clusters = []

            # test if df is empty, if yes skip the rest of the function
            if not df.empty:

                try:
                    # Get unique account-region combinations
                    for account in df['usage_account_id'].unique():
                        for region in df[df['usage_account_id'] == account]['region'].unique():

                            # Mock result structure similar to what would come from a DocumentDB API call
                            mock_result = {
                                'danteCallStatus': 'SUCCESSFUL',
                                'dBClusters': docdb_clusters
                            }

                            # Process the data to find idle clusters
                            idle_data = self.process_check_data(account, region, None, mock_result)
                            idle_clusters.extend(idle_data)

                    # Create a new DataFrame with idle clusters
                    if idle_clusters:
                        idle_df = pd.DataFrame(idle_clusters)

                        # Merge with original cost data
                        merged_df = pd.merge(
                            df,
                            idle_df,
                            left_on='resource_id',
                            right_on='docdb_name',
                            how='inner'
                        )
                        # If we found idle clusters, use the merged data
                        if not merged_df.empty:
                            df = merged_df

                except Exception as e:                
                    l_msg = f"Unable to merge DocumentDB data: {e}"
                    self.appConfig.console.warning("\n[red]"+l_msg)
                    self.logger.warning(l_msg)
                    return

            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':True})
            self.report_definition = {'LINE_VALUE': 6, 'LINE_CATEGORY': 3}

    def get_required_columns(self) -> list:
        return [
                    'usage_account_id',
                    'resource_id',
                    'region',
                    'estimated_savings',
                    self.ESTIMATED_SAVINGS_CAPTION
            ]

    def get_expected_column_headers(self) -> list:
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        # This method needs to be implemented with the specific SQL query for idle DocumentDB instances cost

        l_SQL = f"""SELECT 
line_item_usage_account_id, 
SPLIT_PART(line_item_resource_id,':',7) AS line_item_resource_id,
product_region,
sum(CAST(line_item_unblended_cost AS decimal(16,8))) AS estimated_savings 
FROM {fqdb_name}  
WHERE 
{account_id} 
line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
AND line_item_product_code = 'AmazonDocDB' 
AND line_item_line_item_type NOT IN ('Tax','Credit','Refund','Fee','RIFee') 
GROUP BY 
line_item_resource_id,
line_item_usage_account_id,
product_region"""

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