# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

"""
Module for handling the Question command in AWS COW.
"""

import sys
import io
import logging
import pandas as pd

from botocore.config import Config as bc_config
from typing import Any
from argparse import Namespace
from abc import abstractmethod

from ..config.config import Config
from ..report_providers.cur_reports.cur import CurReports
from ..genai_providers.genai_providers import GenAIProviders

class QuestionBase:

    def __init__(self):
        pass

    @abstractmethod
    def validate_genai_request(self) -> None:
        """
        Validate the request to ensure it meets the requirements for the Question command.
        Each Question type will need to implement its own validation logic.
        """
        pass

    @abstractmethod
    def execute(self) -> None:
        """
        Execute the Question command.
        """
        pass

    def ask_question(self, question=None):
        """
        Ask the user to type in a question at the keyboard.
        """
        if not question:
            question = "Enter a cost optimization question about your environment (or 'quit' to exit)"

        self.appConfig.console.print(f"[yellow]{question} (or 'quit' to exit): ")
        q = input()
        return q

    def display_answer(self, answer):
        """
        Display the answer on the screen.
        """
        self.appConfig.console.print("[green]Answer:")
        self.appConfig.console.print(answer)

class Question(QuestionBase):
    """
    Command class for handling questions using AWS Bedrock.
    """

    def __init__(self, arguments: Namespace, appInstance):
        #ToDo remove appInstance

        # self.appInstance = appInstance
        self.appConfig = Config()
        self.bc_config = bc_config()
        # self.arguments = arguments
        self.question = None
        self.data_source = 'file'

        # test if arguments has input_files
        if hasattr(arguments, 'input_files'):
            self.input_file = arguments.input_files
        else:
            self.input_file = None

    def _type_of_file(self) -> str:
        if "xlsx" in self.input_file[0].lower():
                type_of_file = "xlsx"
        elif "xls" in self.input_file[0].lower():
            type_of_file = "xls"
        elif "csv" in self.input_file[0].lower():
            type_of_file = "csv"
        else:
            type_of_file = "txt"
        
        return type_of_file
    
    def _output_location(self) -> str:
        if self.appConfig.arguments_parsed.bucket_for_results:
            return 's3'
        else:
            return 'local'
           
    def _process_question_argument(self) -> None:
        self.question = self.appConfig.arguments_parsed.question or self.ask_question()
        print(f"Question: '{self.question}'")
    
    def validate_genai_request(self) -> None:
        output_location = self._output_location()

        if output_location == 's3':
            #Todo handle questions about data stored in S3.  
            #Currently we can only handle questions about data stored in local file system.
            self.appConfig.console.print(f'[warning]For output delivery to {output_location} location input file is required (-f argument)')
            sys.exit()

        if output_location == 'local':
            if not self.appConfig.arguments_parsed.input_files:
                self.appConfig.console.print(f'[warning]For output delivery to {output_location} location input file is required (-f argument)')
                sys.exit()
            else:
                self._process_question_argument()
       
    def execute(self):
        """
        Execute the Question command with enabled provider.
        """
        # get enabled provider
        self.genai_provider = GenAIProviders()

        # loop until the user stop the process
        while True:

            answer = self.genai_provider.provider.execute(self.question, self.input_file[0], self._type_of_file(), encrypted = False, data_source=self.data_source)

            if answer: 
                self.display_answer(answer)
                self.save_to_file(answer)
            else:
                self.appConfig.console.print(f"[yellow]Resend question: \"{self.question}\" \[y/n]? :")
                resend = input()
                if resend.lower() == 'y':
                    self.appConfig.console.print(f"Resending: \"{self.question}\" ")
                    continue

            # ask the user if it has to break the process, or to ask another question 
            self.question = self.ask_question(question="Please enter another question")
            if self.question == "quit":
                break

    #TODO save to file should into one of the output classes
    def save_to_file(self, answer):
        """
        Save the answer to a file.
        """
        filename = "bedrock_answer.txt"
        with open(filename, "w") as f:
            f.write(answer)
        print(f"Answer saved to {filename}")

class QuestionSQL(QuestionBase):
    """
    Command class for handling SQL questions related to cost optimization in AWS.
    """

    #TODO this needs to be reimplemented where GenAI generates the correct CUR query for us.
    def __init__(self):
        self.appConfig = Config()

    def validate_genai_request(self):
        pass

    def execute(self):
        self.appConfig.console.print(f"[blue]Feature not implemented.  Please use the Question instead.")

    # def __init__(self, arguments: Namespace, appConfig):
    #     self.arguments = arguments
    #     self.appConfig = appConfig
    #     self.cur_reports = CurReports(appConfig)
    #     self.logger = logging.getLogger(__name__)

    # def execute(self):
    #     """
    #     Execute the QuestionSQL command.
    #     """
    #     while True:
    #         question = self.ask_question()
    #         if question.lower() == 'quit':
    #             break

    #         try:
    #             sql_query = self.generate_sql_query(question)
    #             self.log_sql_query(sql_query)
    #             results = self.execute_athena_query(sql_query)
    #             self.display_results(results)
    #         except Exception as e:
    #             self.appConfig.console.print(f"[red]An error occurred: {str(e)}[/red]")

    # def ask_question(self):
    #     """
    #     Ask the user to type in a question related to cost optimization.
    #     """
    #     return input("Enter your cost optimization question (or 'quit' to exit): ")

    # def generate_sql_query(self, question):
    #     """
    #     Generate an SQL query based on the user's question.
    #     This is a basic implementation and can be further improved with NLP techniques.
    #     """
    #     keywords = question.lower().split()
    #     select_clause = "SELECT "
    #     from_clause = f"FROM {self.cur_reports.fqdb_name}"
    #     where_clause = "WHERE "
    #     group_by_clause = ""
    #     order_by_clause = ""

    #     if "total" in keywords or "sum" in keywords:
    #         select_clause += "SUM(line_item_unblended_cost) as total_cost, "
    #     if "average" in keywords or "avg" in keywords:
    #         select_clause += "AVG(line_item_unblended_cost) as average_cost, "
    #     if "service" in keywords:
    #         select_clause += "line_item_product_code, "
    #         group_by_clause = "GROUP BY line_item_product_code"
    #         order_by_clause = "ORDER BY total_cost DESC"
    #     if "region" in keywords:
    #         select_clause += "product_region, "
    #         group_by_clause = "GROUP BY product_region"
    #         order_by_clause = "ORDER BY total_cost DESC"
    #     if "account" in keywords:
    #         select_clause += "line_item_usage_account_id, "
    #         group_by_clause = "GROUP BY line_item_usage_account_id"
    #         order_by_clause = "ORDER BY total_cost DESC"

    #     select_clause = select_clause.rstrip(", ")
    #     if not group_by_clause:
    #         group_by_clause = "GROUP BY line_item_usage_start_date"
    #         order_by_clause = "ORDER BY line_item_usage_start_date"

    #     if "last month" in question.lower():
    #         where_clause += "line_item_usage_start_date >= DATE_ADD('month', -1, CURRENT_DATE)"
    #     elif "last week" in question.lower():
    #         where_clause += "line_item_usage_start_date >= DATE_ADD('week', -1, CURRENT_DATE)"
    #     else:
    #         where_clause += "line_item_usage_start_date >= DATE_ADD('month', -3, CURRENT_DATE)"

    #     query = f"{select_clause} {from_clause} {where_clause} {group_by_clause} {order_by_clause} LIMIT 100"
    #     return query

    # def log_sql_query(self, query):
    #     """
    #     Log the generated SQL query.
    #     """
    #     self.logger.info(f"Generated SQL query: {query}")

    # def execute_athena_query(self, query):
    #     """
    #     Execute the SQL query using Athena.
    #     """
    #     try:
    #         execution_id = self.cur_reports.start_query_execution(query)
    #         return self.cur_reports.get_query_results(execution_id)
    #     except Exception as e:
    #         self.logger.error(f"Error executing Athena query: {e}")
    #         raise

    # def display_results(self, results):
    #     """
    #     Display the query results on the console.
    #     """
    #     if results and 'ResultSet' in results:
    #         columns = [col['Label'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
    #         rows = results['ResultSet']['Rows'][1:]  # Skip the header row

    #         table = self.appConfig.rich_table.Table(title="Query Results")
    #         for column in columns:
    #             table.add_column(column, style="cyan")

    #         for row in rows:
    #             table.add_row(*[data.get('VarCharValue', '') for data in row['Data']])

    #         self.appConfig.console.print(table)
    #     else:
    #        self.appConfig.console.print("[red]No results or an error occurred.[/red]")