# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

"""
Factory module for creating command objects based on CLI arguments.
This module implements the Factory pattern to instantiate the appropriate command class.
"""

import sys
from argparse import Namespace
from .available_reports import AvailableReportsCommand
from .configure_tooling import ConfigureToolingCommand
from .run_tooling import RunToolingRun
from .version import VersionCommand
from .gimport_conf import ImportConfCommand
from .gexport_conf import ExportConfCommand
from .question import Question, QuestionSQL

class NotImplementedException(Exception):
    pass

class CommandFactory:
    """
    Factory class for creating command objects based on CLI arguments.
    """

    @classmethod
    def create(cls, arguments: Namespace, app):
        """
        Create and return a command object based on the given arguments.
        
        :param arguments: Parsed command line arguments
        :param app: The application instance
        :return: A command object
        """
        """
        Create and return the appropriate command object based on the provided arguments.

        Args:
            arguments (Namespace): Parsed command-line arguments
            app: The main application object

        Returns:
            Command object instance corresponding to the given arguments
        """
        _class = None
        
        # Determine the appropriate command class based on the arguments
        if arguments.version is True:
            _class = VersionCommand(app)
        elif arguments.dump_configuration or arguments.ls_conf:
            _class = ExportConfCommand(app)
        elif arguments.import_dump_configuration:
            _class = ImportConfCommand(app)
        elif arguments.configure:
            _class = ConfigureToolingCommand()
        elif arguments.available_reports:
            _class = AvailableReportsCommand(app)
        elif arguments.question:
            _class = Question(arguments,app)
        elif arguments.question_sql:
            _class = QuestionSQL()
        elif arguments.ce:
            _class = RunToolingRun(app)
        elif arguments.co:
            _class = RunToolingRun(app)
        elif arguments.ta:
            _class = RunToolingRun(app)
        elif arguments.cur:
            _class = RunToolingRun(app)
        else:
            sys.exit()

        # Instantiate and return the selected command class
        return _class
