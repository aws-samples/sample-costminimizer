# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

"""
Module for handling the Question command in AWS COW.
"""

import pandas as pd
import io
from botocore.config import Config
from argparse import Namespace
import logging

from ..report_providers.cur_reports.cur import CurReports
from ..report_output_handler.report_output_gen_ai import ReportOutputGenAi


class Question:
    """
    Command class for handling questions using AWS Bedrock.
    """

    def __init__(self, arguments: Namespace, appInstance):
        self.arguments = arguments
        self.appInstance = appInstance
        self.appConfig = appInstance.config_manager.appConfig
        self.config = Config()
        self.question = arguments.question
        self.data_source = 'file'

        # test if arguments has input_files
        if hasattr(arguments, 'input_files'):
            self.input_files = arguments.input_files
        else:
            self.input_files = None

    def execute(self):
        """
        Execute the Question command.
        """
        # TODO: Implement the logic to send the question to Bedrock and process the response
        self.rpt = ReportOutputGenAi( self.appConfig)

        # Increase the read timeout to 300 seconds (5 minutes)
        self.config.read_timeout=300
        self.config.connect_timeout=300

        self.rpt._initiate_ai_client('bedrock-runtime', self.config, 'us-east-1')

        # loop until the user stop the process
        while True:

            answer = self.send_to_bedrock( self.rpt, self.question, self.input_files)

            self.display_answer(answer)
            self.save_to_file(answer)

            # ask the user if it has to break the process, or to ask another question 
            self.question = self.ask_question()
            if self.question == "quit":
                break

    # function that ask the user to type in a question at the keyboard
    def ask_question(self):
        """
        Ask the user to type in a question at the keyboard.
        """
        # TODO: Implement the logic to ask the user to type in a question at the keyboard
        # This is a placeholder implementation
        self.appConfig.console.print("[yellow]Please enter another question? (or type quit to stop)")
        question = input()
        return question


    def send_to_bedrock(self, rpt, question, input_files):
        """
        Send the question to AWS Bedrock and get the response.
        """
        # TODO: Implement the actual call to AWS Bedrock
        # This is a placeholder implementation

        if input_files:
            # test if input_files contains xlsx or xls not matter the CAPS for the chars
            if "xlsx" in input_files[0].lower():
                type_of_file = "xlsx"
            elif "xls" in input_files[0].lower():
                type_of_file = "xls"
            elif "csv" in input_files[0].lower():
                type_of_file = "csv"
            else:
                type_of_file = "txt"

            # Convert input files to base64
            if self.data_source == 'file':
                base64_file = rpt._convert_file_to_base64(input_files[0])
            else:  
                df = pd.DataFrame(input_files)
                io_writer = io.BytesIO()
                df.to_csv(io_writer)
                io_writer.seek(0)
                base64_file = io_writer.getvalue()
        else:
            base64_file = None
            type_of_file = None

        with self.appConfig.console.status(f'Fetching results from GenAI (this may take a while)...'):
            answer = rpt._generate_ai_data_question(self.appConfig, input_text = question, file_binary = base64_file, file_format = type_of_file)
        l_answer = f"This is a placeholder answer for the question: {answer}"

        return l_answer

    def display_answer(self, answer):
        """
        Display the answer on the screen.
        """
        self.appConfig.console.print("[green]Answer:")
        self.appConfig.console.print(answer)

    def save_to_file(self, answer):
        """
        Save the answer to a file.
        """
        filename = "bedrock_answer.txt"
        with open(filename, "w") as f:
            f.write(answer)
        print(f"Answer saved to {filename}")

class QuestionSQL:
    """
    Command class for handling SQL questions related to cost optimization in AWS.
    """

    def __init__(self, arguments: Namespace, appConfig):
        self.arguments = arguments
        self.appConfig = appConfig
        self.cur_reports = CurReports(appConfig)
        self.logger = logging.getLogger(__name__)

    def execute(self):
        """
        Execute the QuestionSQL command.
        """
        while True:
            question = self.ask_question()
            if question.lower() == 'quit':
                break

            try:
                sql_query = self.generate_sql_query(question)
                self.log_sql_query(sql_query)
                results = self.execute_athena_query(sql_query)
                self.display_results(results)
            except Exception as e:
                self.appConfig.console.print(f"[red]An error occurred: {str(e)}[/red]")

    def ask_question(self):
        """
        Ask the user to type in a question related to cost optimization.
        """
        return input("Enter your cost optimization question (or 'quit' to exit): ")

    def generate_sql_query(self, question):
        """
        Generate an SQL query based on the user's question.
        This is a basic implementation and can be further improved with NLP techniques.
        """
        keywords = question.lower().split()
        select_clause = "SELECT "
        from_clause = f"FROM {self.cur_reports.fqdb_name}"
        where_clause = "WHERE "
        group_by_clause = ""
        order_by_clause = ""

        if "total" in keywords or "sum" in keywords:
            select_clause += "SUM(line_item_unblended_cost) as total_cost, "
        if "average" in keywords or "avg" in keywords:
            select_clause += "AVG(line_item_unblended_cost) as average_cost, "
        if "service" in keywords:
            select_clause += "line_item_product_code, "
            group_by_clause = "GROUP BY line_item_product_code"
            order_by_clause = "ORDER BY total_cost DESC"
        if "region" in keywords:
            select_clause += "product_region, "
            group_by_clause = "GROUP BY product_region"
            order_by_clause = "ORDER BY total_cost DESC"
        if "account" in keywords:
            select_clause += "line_item_usage_account_id, "
            group_by_clause = "GROUP BY line_item_usage_account_id"
            order_by_clause = "ORDER BY total_cost DESC"

        select_clause = select_clause.rstrip(", ")
        if not group_by_clause:
            group_by_clause = "GROUP BY line_item_usage_start_date"
            order_by_clause = "ORDER BY line_item_usage_start_date"

        if "last month" in question.lower():
            where_clause += "line_item_usage_start_date >= DATE_ADD('month', -1, CURRENT_DATE)"
        elif "last week" in question.lower():
            where_clause += "line_item_usage_start_date >= DATE_ADD('week', -1, CURRENT_DATE)"
        else:
            where_clause += "line_item_usage_start_date >= DATE_ADD('month', -3, CURRENT_DATE)"

        query = f"{select_clause} {from_clause} {where_clause} {group_by_clause} {order_by_clause} LIMIT 100"
        return query

    def log_sql_query(self, query):
        """
        Log the generated SQL query.
        """
        self.logger.info(f"Generated SQL query: {query}")

    def execute_athena_query(self, query):
        """
        Execute the SQL query using Athena.
        """
        try:
            execution_id = self.cur_reports.start_query_execution(query)
            return self.cur_reports.get_query_results(execution_id)
        except Exception as e:
            self.logger.error(f"Error executing Athena query: {e}")
            raise

    def display_results(self, results):
        """
        Display the query results on the console.
        """
        if results and 'ResultSet' in results:
            columns = [col['Label'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
            rows = results['ResultSet']['Rows'][1:]  # Skip the header row

            table = self.appConfig.rich_table.Table(title="Query Results")
            for column in columns:
                table.add_column(column, style="cyan")

            for row in rows:
                table.add_row(*[data.get('VarCharValue', '') for data in row['Data']])

            self.appConfig.console.print(table)
        else:
            self.appConfig.console.print("[red]No results or an error occurred.[/red]")