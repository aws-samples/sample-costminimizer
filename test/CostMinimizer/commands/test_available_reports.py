from CostMinimizer.commands.available_reports import AvailableReportsCommand
from CostMinimizer.report_controller.report_controller import CowReportController
from unittest.mock import MagicMock
from unittest.mock import MagicMock, patch
from unittest.mock import Mock
import pytest
from rich.layout import Layout


class TestAvailableReports:

    def test___init___initialization(self):
        """
        Test the initialization of AvailableReportsCommand.

        This test verifies that the AvailableReportsCommand.__init__ method
        correctly initializes the object's attributes when given an appInstance
        and an optional writer.
        """

        # Create a mock appInstance with a config_manager
        mock_app_instance = Mock()
        mock_app_instance.config_manager.appConfig = Mock()

        # Create a mock writer
        mock_writer = Mock()

        # Initialize the AvailableReportsCommand
        command = AvailableReportsCommand(mock_app_instance, writer=mock_writer)

        # Assert that the attributes are correctly set
        assert command.appInstance == mock_app_instance
        assert command.appConfig == mock_app_instance.config_manager.appConfig
        assert isinstance(command.layout, Layout)
        assert command.writer == mock_writer

        # Test initialization without a writer
        command_no_writer = AvailableReportsCommand(mock_app_instance)
        assert command_no_writer.writer is None

    def test___init___invalid_app_instance(self):
        """
        Test initializing AvailableReportsCommand with an invalid app instance.
        This test verifies that the __init__ method handles the case where
        the provided appInstance does not have the expected attributes.
        """
        class InvalidAppInstance:
            pass

        with pytest.raises(AttributeError):
            AvailableReportsCommand(InvalidAppInstance())

    def test_get_all_available_reports_1(self):
        """
        Test that get_all_available_reports returns a list of all available reports
        from all report providers.
        """
        # Create a mock AppConfig
        mock_app_config = MagicMock()

        # Create an instance of AvailableReportsCommand
        available_reports_command = AvailableReportsCommand(MagicMock(config_manager=MagicMock(appConfig=mock_app_config)))

        # Mock the get_report_providers method
        mock_provider1 = MagicMock()
        mock_provider2 = MagicMock()
        available_reports_command.get_report_providers = MagicMock(return_value=[mock_provider1, mock_provider2])

        # Mock the get_available_reports method for each provider
        mock_report1 = MagicMock()
        mock_report2 = MagicMock()
        mock_report3 = MagicMock()
        mock_provider1.return_value.get_available_reports.return_value = [mock_report1, mock_report2]
        mock_provider2.return_value.get_available_reports.return_value = [mock_report3]

        # Call the method under test
        result = available_reports_command.get_all_available_reports()

        # Assert that the result is a list containing all mock reports
        assert result == [mock_report1, mock_report2, mock_report3]

        # Verify that the methods were called as expected
        available_reports_command.get_report_providers.assert_called_once()
        mock_provider1.assert_called_once_with(mock_app_config)
        mock_provider2.assert_called_once_with(mock_app_config)
        mock_provider1.return_value.get_available_reports.assert_called_once_with(return_available_report_objects=True)
        mock_provider2.return_value.get_available_reports.assert_called_once_with(return_available_report_objects=True)

    def test_get_all_available_reports_empty_providers(self):
        """
        Test the scenario where get_report_providers returns an empty list.
        This tests the edge case of having no report providers available.
        """
        mock_app_instance = MagicMock()
        mock_config = MagicMock()
        mock_app_instance.config_manager.appConfig = mock_config

        command = AvailableReportsCommand(mock_app_instance)

        # Mock get_report_providers to return an empty list
        command.get_report_providers = MagicMock(return_value=[])

        result = command.get_all_available_reports()

        assert isinstance(result, list), "Result should be a list"
        assert len(result) == 0, "Result should be an empty list when no providers are available"


    def test_run_2(self):
        """
        Test the run method when the application mode is 'module'.

        This test verifies that the run method returns all_available_reports
        when the application mode is set to 'module'.
        """
        # Mock the necessary dependencies
        mock_app_instance = MagicMock()
        mock_app_instance.AppliConf.mode = 'module'
        mock_config = MagicMock()
        mock_app_instance.config_manager.appConfig = mock_config

        # Create an instance of AvailableReportsCommand
        command = AvailableReportsCommand(mock_app_instance)

        # Mock the CowReportController and its methods
        with patch('CostMinimizer.commands.available_reports.CowReportController') as mock_controller:
            mock_controller_instance = mock_controller.return_value
            mock_controller_instance.import_reports.return_value = [MagicMock()]

            # Mock the provider and its methods
            mock_provider = MagicMock()
            mock_provider.return_value.get_available_reports.return_value = [MagicMock()]

            # Run the method
            result = command.run()

        # Assert that the result is a dictionary (all_available_reports)
        assert isinstance(result, dict)
        # Assert that the result is not empty
        assert len(result) > 0

    def test_run_3(self):
        """
        Test the run method when the application mode is 'cli'.

        This test verifies that when the AppliConf.mode is set to 'cli',
        the method correctly displays the available reports and their details,
        without returning any value.
        """
        # Mock the necessary dependencies
        mock_app_instance = MagicMock()
        mock_app_instance.AppliConf.mode = 'cli'
        mock_config = MagicMock()
        mock_app_instance.config_manager.appConfig = mock_config

        # Create an instance of AvailableReportsCommand
        command = AvailableReportsCommand(mock_app_instance)

        # Mock the CowReportController and its methods
        with patch('CostMinimizer.commands.available_reports.CowReportController') as mock_controller:
            mock_provider = MagicMock()
            mock_report = MagicMock()
            mock_controller.return_value.import_reports.return_value = [mock_provider]
            mock_provider.return_value.get_available_reports.return_value = [mock_report]

            # Call the run method
            result = command.run()

            # Assert that the necessary methods were called
            mock_controller.return_value.import_reports.assert_called_once_with(force_all_providers_true=True)
            mock_provider.return_value.get_available_reports.assert_called_once_with(return_available_report_objects=True)

            # Assert that the console methods were called to display information
            mock_config.console.rule.assert_called_once()
            mock_config.console.print.assert_called()

            # Assert that no value is returned when in 'cli' mode
            assert result is None

    def test_run_cli_and_module_modes(self):
        """
        Test the run method of AvailableReportsCommand for both CLI and module modes.

        This test verifies:
        1. The correct behavior when self.appInstance.AppliConf.mode is 'cli'
        2. The correct behavior when self.appInstance.AppliConf.mode is 'module'
        3. The method returns all_available_reports when in 'module' mode
        """
        # Mock dependencies
        mock_app_instance = MagicMock()
        mock_writer = MagicMock()
        mock_app_config = MagicMock()
        mock_console = MagicMock()
        mock_layout = MagicMock()

        # Set up the AvailableReportsCommand instance
        command = AvailableReportsCommand(mock_app_instance, mock_writer)
        command.appConfig = mock_app_config
        command.appConfig.console = mock_console
        command.layout = mock_layout

        # Mock CowReportController and its method
        mock_provider = MagicMock()
        mock_report = MagicMock()
        mock_provider.return_value.get_available_reports.return_value = [mock_report]

        with patch('CostMinimizer.commands.available_reports.CowReportController') as mock_controller:
            mock_controller.return_value.import_reports.return_value = [mock_provider]

            # Test CLI mode
            mock_app_instance.AppliConf.mode = 'cli'
            command.run()

            # Verify CLI mode behavior
            mock_console.rule.assert_called_once()
            mock_layout.split_row.assert_called_once()
            mock_console.print.assert_called()

            # Test module mode
            mock_app_instance.AppliConf.mode = 'module'
            result = command.run()

            # Verify module mode behavior
            assert isinstance(result, dict)
            assert mock_provider in result
            assert result[mock_provider] == [mock_report]


