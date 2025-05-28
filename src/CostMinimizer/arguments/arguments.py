# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from importlib.metadata import metadata
# Then you can access package metadata like this:
package_metadata = metadata('CostMinimizer')

"""
Handles command-line argument parsing for the Cost Optimization Tooling.
This class processes raw arguments and provides methods to parse and manage various options.
"""

import logging
from argparse import ArgumentParser
from colorama import init, Fore, Style

from ..patterns.singleton import Singleton

# Initialize colorama
init(autoreset=True)

class ToolingArguments(Singleton):

    def __init__(self) -> None:
        
        self.logger = logging.getLogger(__name__)  # Logger for this class
        self.raw_arguments = None  # Store the original command-line arguments
        self._argument_parser = None  # Will hold the parsed arguments
        self.selected_customer = None  # Placeholder for selected customer information
        self.parser = None  # Will hold the ArgumentParser object

    def command_line_arguments(self, raw_arguments):
        """
        Parse command line arguments for the Cost Optimization tooling.

        Args:
            report_input_file (str): Path to the report input file, if provided.

        Returns:
            argparse.Namespace: Parsed command-line arguments.
        """
        self.raw_arguments = raw_arguments

        # Create the main ArgumentParser object
        parser = ArgumentParser()

        # TODO most arguments should have a default of False, where it makes sense
        parser = ArgumentParser(description=f'{Fore.CYAN}CostMinimizer - Cost Optimization Tooling{Style.RESET_ALL}')

        # Accounts and Payer are considered mutually exclusive in the QueryCommand class
        # TODO: Add mutex logic here in command line parsing for mutually exclusive arguments

        # -a --available-reports; Report-related arguments
        parser.add_argument(
            '-a', '--available-reports', action='store_true',
            help=f"{Fore.GREEN}Output a list of all available reports{Style.RESET_ALL}",
            default=False)

        # -b --bucket-for-results; Add S3 bucket parameter for storing results
        parser.add_argument(
            '-b', '--bucket-for-results', type=str,
            help=f"{Fore.GREEN}Specify an S3 bucket to store results instead of local storage{Style.RESET_ALL}",
            default=None)

        # -e --ce; Cost Explorer
        parser.add_argument(
            '-e', '--ce', action='store_true',
            help=f"{Fore.GREEN}Run Cost Explorer reports{Style.RESET_ALL}",
            default=False)

        # -c --customer; Customer-related arguments
        parser.add_argument(
            '-c', '--customer', type=str,
            help=f"{Fore.GREEN}Specify a customer to run the tooling for{Style.RESET_ALL}",
            default=None)
        
        # -f --input-files
        parser.add_argument(
            '-f', '--input-files', nargs='+',
            help=f"{Fore.GREEN}Specify an XLS that contains Cost Optimizations informations, sent along with the question ({Fore.YELLOW}-q QUESTION{Fore.GREEN} option){Style.RESET_ALL}",
            default=[])

        #-g --configure
        parser.add_argument(
            '-g','--configure', action='store_true',
            help=f"{Fore.GREEN}Launch configuration wizard{Style.RESET_ALL}",
            default=False)

        # --ls-conf; List all values of the configuration table
        parser.add_argument(
            '--ls-conf', action='store_true',
            help=f"{Fore.GREEN}List all values of the configuration of the tooling{Style.RESET_ALL}",
            default=None)

        # --auto-updaet-conf; Auto update configuration table based on AWS credentials
        parser.add_argument(
            '--auto-update-conf', action='store_true',
            help=f"{Fore.GREEN}Auto update the values of the configuration of the tooling{Style.RESET_ALL}",
            default=None)

        # -i --import-dump-configuration; Configuration-related arguments
        parser.add_argument(
            '-i', '--import-dump-configuration', action='store_true',
            help=f"{Fore.GREEN}Import existing CostMinimizer Tooling configuration from existing file{Style.RESET_ALL}",
            default=False)

        # -o --co; Compute Optimizer
        parser.add_argument(
            '-o', '--co', action='store_true',
            help=f"{Fore.GREEN}Run Compute Optimizer reports{Style.RESET_ALL}",
            default=False)

        # -p --dump-configuration; Utility arguments
        parser.add_argument(
            '-p', '--dump-configuration', action='store_true',
            help=f"{Fore.GREEN}Export CostMinimizer Tooling configuration into a file{Style.RESET_ALL}",
            default=False)

        # -q --question; Any question can be sent to Q or BedRock and the answer is displayed on the screen
        parser.add_argument(
            '-q', '--question', type=str,
            help=f"{Fore.GREEN}Enter a question to ask genAI BedRock{Style.RESET_ALL}",
            default=None)

        # -l --question-sql; Any SQL question can be sent to Q or BedRock and the answer is displayed on the screen
        parser.add_argument(
            '-l', '--question-sql', action='store_true',
            help=f"{Fore.GREEN}Option used with {Fore.YELLOW}-q QUESTION{Fore.GREEN} to ask genAI BedRock for SQL equivalent text request and send it to Athena to get the result{Style.RESET_ALL}",
            default=None)

        # Option to specify that once the XLS Cost Optimization files are generated locally, 
        # then ask genAI to generate recommendations
        # -r --genai-recommendations
        parser.add_argument(
            '-r', '--genai-recommendations', action='store_true',
            help=f"{Fore.GREEN}Ask genAI to generate a PowerPoint files with cost optimization recommendations based on the XLS results{Style.RESET_ALL}",
            default=False)

        # Option that tell that an email has to be sent once the XLS Cost Optimization file 
        # has been generated
        # -s --send_mail
        parser.add_argument(
            '-s', '--send_mail', type=str,
            help=f"{Fore.GREEN}Email address to send the XLS report automatically{Style.RESET_ALL}",
            default=None)

        # -t --ta; Trusted Advisor
        parser.add_argument(
            '-t', '--ta', action='store_true',
            help=f"{Fore.GREEN}Run Trusted Advisor reports{Style.RESET_ALL}",
            default=False)

        # -u --cur; CUR
        parser.add_argument(
            '-u', '--cur', action='store_true',
            help=f"{Fore.GREEN}Run Cost & Usage Report{Style.RESET_ALL}",
            default=False)

        # --cur-db; CUR database and table override parameters
        parser.add_argument(
            '--cur-db', type=str,
            help=f"{Fore.GREEN}Override the CUR database name configured in the internal settings{Style.RESET_ALL}",
            default=None)
        
        # --cur-table
        parser.add_argument(
            '--cur-table', type=str,
            help=f"{Fore.GREEN}Override the CUR table name configured in the internal settings{Style.RESET_ALL}",
            default=None)
            
        # --cur-month-date-minus-x
        parser.add_argument(
            '--cur-month-date-minus-x', type=int,
            help=f"{Fore.GREEN}Select data from X months before the latest month in CUR table{Style.RESET_ALL}",
            default=0)

        # --checks; Add checks parameter to skip menu selection
        parser.add_argument(
            '--checks', nargs='+',
            help=f"{Fore.GREEN}Specify a list of checks to run, bypassing the menu selection{Style.RESET_ALL}",
            default=None)

        # --region; Add region parameter
        parser.add_argument(
            '--region', type=str,
            help=f"{Fore.GREEN}Specify the AWS region to use for executing the code{Style.RESET_ALL}",
            default=None)
        
        # --profile; Add profile parameter
        parser.add_argument(
            '--profile', type=str,
            help=f"{Fore.GREEN}Specify the AWS profile to use for credentials{Style.RESET_ALL}",
            default=None)

        # -v --version; Display the version of the tool
        parser.add_argument(
            '-v', '--version', action='store_true',
            help=f"{Fore.GREEN}Display the current version of {__tooling_name__} Tooling{Style.RESET_ALL}", default=False)

        # Store the parser and parse the arguments
        self.parser = parser
        self._argument_parser = self.parser.parse_args(self.raw_arguments)

        return self._argument_parser

    def set_data_request_type(self) -> str:
        """
        Set the data request type based on parsed arguments.

        Args:
            parsed_arguments (argparse.Namespace): The parsed command-line arguments.

        Returns:
            str: The data request type, always 'run' in this implementation.
        """
        # Currently, this method always returns 'run'. It might be extended in the future for different request types.
        data_request_type = 'run'
        return data_request_type





    
