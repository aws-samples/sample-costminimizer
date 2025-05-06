# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

# Import necessary modules and base class
from ..cur_base import CurBase  # Import the base class for CUR reports
import pandas as pd  # For data manipulation and analysis
import sqlparse  # For SQL query formatting
import time  # For handling time-related operations in Athena queries
from rich.progress import track

class CurInteraztraffic(CurBase):
    """
    A class for generating reports on Inter-AZ traffic based on AWS Cost and Usage Report (CUR) data.
    This class extends CurBase and provides methods for querying and processing data related to
    Inter-AZ traffic costs and usage.

    The report focuses on identifying resources that generate significant Inter-AZ traffic,
    which can help in optimizing network usage and potentially reducing associated costs.

    This class is part of a larger system for analyzing AWS costs and usage. It specifically
    targets inter-Availability Zone (AZ) data transfer, which can be a significant cost factor
    in multi-AZ deployments.

    Key features:
    - Queries AWS Athena to retrieve CUR data
    - Processes and formats the data into a pandas DataFrame
    - Provides methods for report customization and data retrieval

    Note: This report does not calculate direct cost savings but provides insights for
    potential cost optimization strategies.

    Attributes:
        ESTIMATED_SAVINGS_CAPTION (str): A class-level constant representing the column name
                                         for estimated savings in the report. This is typically
                                         set by the parent CurBase class. For this report, it's
                                         used to maintain consistency with other reports, even
                                         though no direct savings are calculated.
        app (object): An application context object, typically set during initialization,
                      which provides access to configuration and utilities.
        report_result (list): A list to store the processed report data. Each item in this list
                              is typically a dictionary containing the report name, data, and type.
    """

    # Class-level attributes are typically defined here, if any exist beyond those inherited from CurBase
    # Note: The ESTIMATED_SAVINGS_CAPTION is likely inherited from CurBase and used here for consistency

    def name(self):
        """Returns the name of the report."""
        return "cur_interaztraffic"

    def common_name(self):
        """Returns a human-readable name for the report."""
        return "Inter-AZ Traffic"

    def service_name(self):
        """Returns the name of the AWS service this report is based on."""
        return "Cost & Usage Report"

    def domain_name(self):
        """Returns the domain this report belongs to."""
        return 'NETWORK'

    def description(self):
        """Provides a brief description of the report's purpose."""
        return "Identifies top resources generating Inter-AZ traffic"

    def long_description(self):
        """Provides a more detailed description of the report's purpose and functionality."""
        return f'''This report identifies the top resources generating Inter-AZ traffic based on usage and cost.
        It can help in understanding network usage patterns and optimizing costs associated with data transfer between Availability Zones.'''

    def author(self) -> list: 
        """Returns a list of authors for this report."""
        return ['AI Assistant']

    def report_provider(self):
        """Specifies the data source provider for this report."""
        return "cur"

    def report_type(self):
        """Specifies the type of report (raw or processed)."""
        return "processed"

    def disable_report(self):
        """
        Determines whether this report should be disabled.
        
        Returns:
        bool: False, indicating that this report is enabled by default.
        """
        return False

    def _set_recommendation(self):
        self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend. No estimated savings recommendation is provided by this report.  Query provides account information useful for cost optimization.'''

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

    def calculate_savings(self):
        """
        Calculates and returns any potential savings.
        
        For the Inter-AZ traffic report, this method doesn't calculate actual savings.
        Instead, it returns the original dataframe, which contains information about
        Inter-AZ traffic usage and costs. This information can be used to identify
        potential areas for optimization, but doesn't represent direct savings.

        Returns:
        pandas.DataFrame: The report dataframe without any savings calculations.
        """
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
        """
        Counts the number of rows in the report dataframe.
        Returns 0 if an error occurs during the process.
        """
        try:
            return self.report_result[0]['Data'].shape[0]
        except:
            return 0

    def run_athena_query(self, athena_client, query, s3_results_queries, athena_database):
        """
        Executes an Athena query and retrieves the results.
        
        Args:
        athena_client: The Athena client to use for query execution.
        query: The SQL query to execute.
        s3_results_queries: The S3 bucket to store query results.
        athena_database: The Athena database to query against.

        Returns:
        The query results if successful.

        Raises:
        Exception: If the query fails to execute successfully.
        """
        try:
            # Start the query execution
            # This initiates the Athena query and specifies where to store the results
            response = athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={
                    'Database': athena_database  # Specify the database to query against
                },
                ResultConfiguration={
                    'OutputLocation': s3_results_queries  # Specify where to store the query results in S3
                }
            )
        except Exception as e:
            raise e
        
        # Get the query execution ID
        # This ID is used to track the query's progress and retrieve results
        query_execution_id = response['QueryExecutionId']
        self.query_id = query_execution_id
        
        # Wait for the query to complete
        # This loop checks the query status periodically until it's no longer running
        while True:
            # Check the status of the query execution
            response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            state = response['QueryExecution']['Status']['State']
            
            # If the query has finished (successfully or not), break the loop
            if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            
            # Wait for 1 second before checking again to avoid overwhelming the Athena service
            # This introduces a small delay between status checks
            # Note: For long-running queries, consider implementing a more sophisticated
            # polling mechanism with exponential backoff to reduce API calls
            time.sleep(1)
        
        # If the query succeeded, fetch and return the results
        if state == 'SUCCEEDED':
            # Retrieve the query results
            # This gets the actual data returned by the query
            response = athena_client.get_query_results(QueryExecutionId=query_execution_id)
            # Extract the rows from the result set
            # The 'Rows' key contains the actual data we're interested in
            results = response['ResultSet']['Rows']
            return results
        else:
            # If the query failed, log the error and raise an exception
            # This provides information about why the query failed
            l_msg = f"Query failed with state: {response['QueryExecution']['Status']['StateChangeReason']}"
            raise Exception(l_msg)

    def addCurReport(self, client, p_SQL, range_categories, range_values, list_cols_currency, group_by, display = False, report_name = ''):
        self.graph_range_values_x1, self.graph_range_values_y1, self.graph_range_values_x2,  self.graph_range_values_y2 = range_values
        self.graph_range_categories_x1, self.graph_range_categories_y1, self.graph_range_categories_x2,  self.graph_range_categories_y2 = range_categories
        """
        Executes an Athena query and processes the results to create a report.

        This method performs the following steps:
        1. Executes the provided SQL query using the Athena client.
        2. Processes the query results into a list of dictionaries.
        3. Creates a pandas DataFrame from the processed data.
        4. Appends the DataFrame to the report_result list.

        Args:
        client: The Athena client to use for query execution.
        p_SQL: The SQL query to execute.

        Side effects:
        - Populates the report_result list with the processed data.
        - Prints a message if no resources are found.
        """
        self.list_cols_currency = list_cols_currency
        self.group_by = group_by
        # The 'results' list below is initialized but not used in this method.
        # It's kept for potential future use or compatibility with other methods.
        # Consider removing if it's confirmed to be unnecessary.
        self.set_chart_type_of_excel()

        # Execute Athena request defined by p_SQL SQL query and get the results
        # This calls the run_athena_query method to execute the query and retrieve results
        try:
            cur_db = self.appConfig.cur_db_arguments_parsed if (hasattr(self.appConfig, 'cur_db_arguments_parsed') and self.appConfig.cur_db_arguments_parsed is not None) else self.appConfig.config['cur_db']
            response = self.run_athena_query(client, p_SQL, self.appConfig.config['cur_s3_bucket'], cur_db)
        except Exception as e:
            l_msg = f"Athena Query failed with state: {e} - Verify tooling CUR configuration via --configure"
            self.appConfig.console.print("\n[red]"+l_msg)
            self.logger.error(l_msg)
            return

        data_list = []  # Initialize an empty list to store processed data

        if len(response) == 0:
            # If no results were returned, print a message
            print(f"No resources found for athena request {p_SQL}.")
        else:
            # Skip the first row (headers) and process each subsequent row
            if display:
                display_msg = f'[green]Running Cost & Usage Report: {report_name} / {self.appConfig.selected_regions[0]}[/green]'
            else:
                display_msg = ''
            for resource in track(response[1:], description=display_msg):
                # Create a dictionary for each row, mapping column names to values
                # This step transforms the Athena query results into a format suitable for a pandas DataFrame
                data_dict = {
                    self.get_required_columns()[0]: resource['Data'][0]['VarCharValue'] if 'VarCharValue' in resource['Data'][0] else '',
                    self.get_required_columns()[1]: resource['Data'][1]['VarCharValue'] if 'VarCharValue' in resource['Data'][1] else '',
                    self.get_required_columns()[2]: resource['Data'][2]['VarCharValue'] if 'VarCharValue' in resource['Data'][2] else '',
                    self.get_required_columns()[3]: resource['Data'][3]['VarCharValue'] if 'VarCharValue' in resource['Data'][3] else 0, 
                    self.get_required_columns()[4]: resource['Data'][4]['VarCharValue'] if 'VarCharValue' in resource['Data'][4] else 0.0

                }
                data_list.append(data_dict)

            # Create a pandas DataFrame from the list of dictionaries
            # This converts our processed data into a format that's easy to work with and analyze
            # Note: For very large datasets, consider using more memory-efficient methods or
            # processing data in chunks to avoid potential memory issues
            df = pd.DataFrame(data_list)
            
            # Append the DataFrame to the report_result list
            # This adds the processed data to the class's report_result attribute for later use
            self.report_result.append({'Name': self.name(), 'Data': df, 'Type': self.chart_type_of_excel, 'DisplayPotentialSavings':False})
            self.report_definition = {'LINE_VALUE': 5, 'LINE_CATEGORY': 3}

        # Note: The 'results' list is initialized but not used in this method.
        # It might be intended for future use or could be removed if it's confirmed to be unnecessary.

    def get_required_columns(self) -> list:
        """
        Returns a list of column names required for the report.

        This method defines the structure of the report by specifying the required columns.

        Returns:
        list: A list of column names (strings) that the report should include.
        """
        return [
            'usage_account_id',
            'resource_id',
            'usage_type',
            'usage',
            'cost'
            #self.ESTIMATED_SAVINGS_CAPTION
        ]

    def get_expected_column_headers(self) -> list:
        """
        Returns the expected column headers for the report.
        In this case, it's the same as the required columns.

        Returns:
        list: A list of column headers (strings) expected in the report.
        """
        return self.get_required_columns()

    def sql(self, fqdb_name: str, payer_id: str, account_id: str, region: str, max_date: str):
        """
        Generates the SQL query for retrieving Inter-AZ traffic data.

        This method constructs an SQL query to fetch data about Inter-AZ traffic from the AWS Cost and Usage Report.
        The query focuses on usage and cost data for data transfer between Availability Zones.

        line_item_usage_account_id,  -- AWS account ID
        line_item_resource_id,       -- Resource identifier (e.g., EC2 instance ID)
        line_item_usage_type,        -- Type of usage (focuses on DataTransfer-Regional-Bytes)
        SUM(line_item_usage_amount) as USAGE,  -- Total data transfer amount
        SUM(line_item_unblended_cost) as COST  -- Total cost of data transfer

        Args:
        fqdb_name (str): The fully qualified database name to query against.

        Returns:
        dict: A dictionary containing the formatted SQL query under the key 'query'.

        SQL Query Explanation:
        - SELECT: Chooses the relevant columns from the CUR data.
        - FROM: Specifies the database table to query.
        - WHERE: Filters for usage line items related to regional data transfer.
        - GROUP BY: Aggregates data by account, resource, and usage type.
        - ORDER BY: Sorts results by cost in descending order to show highest costs first.
        """
        # Construct the SQL query using an f-string for dynamic table name insertion
        l_SQL = f"""SELECT 
line_item_usage_account_id, 
line_item_resource_id, 
line_item_usage_type, 
SUM(line_item_usage_amount) as USAGE, 
SUM(line_item_unblended_cost) as COST 
FROM {fqdb_name} 
WHERE 
{account_id} 
line_item_line_item_type = 'Usage' 
AND line_item_usage_type LIKE '%DataTransfer-Regional-Bytes' 
AND line_item_usage_start_date BETWEEN DATE_ADD('month', -1, DATE('{max_date}')) AND DATE('{max_date}') 
GROUP BY 1,2,3  -- Group by account, resource, and usage type (using column positions for brevity and potential performance benefits)
ORDER BY SUM(line_item_unblended_cost) DESC"""

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
        return 3, 0, 3, 0

    # return list of columns values in the excel graph, which is the Column # in excel sheet from [0..N]
    def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
        return 4, 1, 4, -1

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
    def get_list_cols_currency(self):
        # [Col1, ..., ColN]
        return [4]

    # return column to group by in the excel graph, which is the rank in the pandas DF [1..N]
    def get_group_by(self):
        # [ColX]
        return [2]