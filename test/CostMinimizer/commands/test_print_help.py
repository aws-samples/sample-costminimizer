from CostMinimizer.commands.print_help import PrintHelpCommand
from unittest.mock import Mock
import pytest

class TestPrintHelp:

    def test___init___initializes_appConfig(self):
        """
        Test that the __init__ method of PrintHelpCommand correctly initializes the appConfig attribute.
        """
        mock_app_config = object()
        command = PrintHelpCommand(mock_app_config)
        assert command.appConfig == mock_app_config


    def test_run_prints_help(self):
        """
        Test that the run method calls print_help on the arguments parser.
        """
        mock_app_config = Mock()
        mock_parser = Mock()
        mock_app_config.get_arguments_parser.return_value = mock_parser

        print_help_command = PrintHelpCommand(mock_app_config)
        print_help_command.run()

        mock_parser.print_help.assert_called_once()

    def test_run_prints_help_2(self):
        """
        Test that the run method calls print_help on the argument parser
        """
        mock_app_config = Mock()
        mock_parser = Mock()
        mock_app_config.get_arguments_parser.return_value = mock_parser

        command = PrintHelpCommand(mock_app_config)
        command.run()

        mock_parser.print_help.assert_called_once()
