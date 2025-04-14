from CostMinimizer.utils.term_menu import launch_terminal_menu
from CostMinimizer.commands.configure_tooling import ConfigureToolingCommand
from CostMinimizer.commands.configure_tooling import ConfigureToolingCommand, CowExportConf
from CostMinimizer.commands.configure_tooling import ConfigureToolingCommand, ErrorInConfigureCowHelper
from CostMinimizer.commands.configure_tooling import ConfigureToolingCommand, ErrorInConfigureCowInsertDB
from CostMinimizer.gexport_conf.gexport_conf import CowExportConf
from CostMinimizer.gimport_conf.gimport_conf import CowImportConf
from botocore.exceptions import ClientError
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import MagicMock, patch
from unittest.mock import Mock, patch
from unittest.mock import patch
from unittest.mock import patch, MagicMock
import ast
import click
import pytest
import sys

class TestConfigureTooling:

    def test___init___1(self):
        """
        Test that the __init__ method of ConfigureToolingCommand correctly initializes
        the instance variables with the provided appInstance.
        """
        # Create a mock appInstance
        mock_app_instance = Mock()
        mock_app_instance.config_manager.appConfig.internals = {
            'internals': {
                'reports': {
                    'reports_module_path': 'test/path'
                }
            }
        }

        # Create an instance of ConfigureToolingCommand
        command = ConfigureToolingCommand(mock_app_instance)

        # Assert that the instance variables are correctly set
        assert command.appInstance == mock_app_instance
        assert command.appConfig == mock_app_instance.config_manager.appConfig
        assert isinstance(command.logger, object)  # Just check if logger is an object
        assert command.module_path == 'test/path'
        assert command.default_report_configs == []

    def test___init___invalid_app_instance(self):
        """
        Test initializing ConfigureToolingCommand with an invalid app instance.
        This test verifies that the __init__ method raises an AttributeError
        when given an app instance that doesn't have the required attributes.
        """
        invalid_app_instance = object()  # An object without config_manager attribute

        with pytest.raises(AttributeError):
            ConfigureToolingCommand(invalid_app_instance)

    def test__configure_report_parameters_1(self):
        """
        Test _configure_report_parameters when report_parameters is empty and a matching report name is found in default configs.

        This test verifies that:
        1. When report_parameters is an empty list
        2. And a matching report name is found in self.default_report_configs
        3. The method correctly extracts and uses the parameters from the default config
        4. It updates the report parameters in the database
        5. It prints a success message
        """
        # Mock objects and setup
        mock_app_config = MagicMock()
        mock_app_instance = MagicMock()
        mock_app_instance.config_manager.appConfig = mock_app_config

        configure_tooling = ConfigureToolingCommand(mock_app_instance)

        # Set up test data
        report_name = "TestReport"
        report_parameters = []
        default_config = {report_name: [{"parameter_name": "TestParam", "current_value": "OldValue", "allowed_values": ["OldValue", "NewValue"]}]}
        configure_tooling.default_report_configs = [str(default_config)]

        # Mock methods
        configure_tooling.report_parameter_menu = MagicMock(return_value="NewValue")
        mock_app_config.database.update_report_parameters = MagicMock()
        mock_app_config.console.print = MagicMock()

        # Call the method
        configure_tooling._configure_report_parameters(report_name, report_parameters)

        # Assertions
        configure_tooling.report_parameter_menu.assert_called_once_with(["OldValue", "NewValue"], "OldValue", "TestParam")
        mock_app_config.database.update_report_parameters.assert_called_once_with(report_name, [{"parameter_name": "TestParam", "current_value": "NewValue", "allowed_values": ["OldValue", "NewValue"]}])
        mock_app_config.console.print.assert_called_once_with(f'[yellow]Parameters for report {report_name} have been updated.')


    def test__configure_report_parameters_3(self):
        """
        Test the _configure_report_parameters method when report_parameters is not an empty list.

        This test verifies that:
        1. The method correctly handles non-empty report_parameters.
        2. It properly processes the report parameters from the input.
        3. It updates the report parameters in the database.
        4. It prints a success message.
        """
        # Setup
        mock_app_config = MagicMock()
        mock_app_instance = MagicMock()
        mock_app_instance.config_manager.appConfig = mock_app_config

        configure_tooling = ConfigureToolingCommand(mock_app_instance)

        report_name = "Test Report"
        report_parameters = [["{'Test Report': [{'parameter_name': 'test_param', 'current_value': 'old_value', 'allowed_values': ['old_value', 'new_value']}]}"]]

        # Mock the report_parameter_menu method
        configure_tooling.report_parameter_menu = MagicMock(return_value='new_value')

        # Execute
        configure_tooling._configure_report_parameters(report_name, report_parameters)

        # Assert
        mock_app_config.database.update_report_parameters.assert_called_once_with(
            report_name,
            [{'parameter_name': 'test_param', 'current_value': 'new_value', 'allowed_values': ['old_value', 'new_value']}]
        )
        mock_app_config.console.print.assert_called_once_with(f'[yellow]Parameters for report {report_name} have been updated.')


    def test_config_report_menu_1(self):
        """
        Test that config_report_menu returns the correct list option when a single report is selected.
        """
        # Create a mock ConfigureToolingCommand instance
        mock_command = MagicMock(spec=ConfigureToolingCommand)

        # Mock the get_config_report_menu_items method to return a list of reports
        mock_command.get_config_report_menu_items.return_value = ['Report 1', 'Report 2', 'Report 3']

        # Mock the launch_terminal_menu function to return a single selected report
        with patch('CostMinimizer.commands.configure_tooling.launch_terminal_menu') as mock_launch_menu:
            mock_launch_menu.return_value = ['Report 2']

            # Call the method under test
            result = ConfigureToolingCommand.config_report_menu(mock_command)

        # Assert that the result is the selected report
        assert result == 'Report 2'

        # Verify that get_config_report_menu_items was called
        mock_command.get_config_report_menu_items.assert_called_once()

        # Verify that launch_terminal_menu was called with the correct arguments
        mock_launch_menu.assert_called_once_with(
            ['Report 1', 'Report 2', 'Report 3'],
            title='Please select the report to configure:',
            subtitle='subtitle',
            multi_select=False,
            show_multi_select_hint=True,
            show_search_hint=True
        )

    def test_export_global_configuration_1(self):
        """
        Test that export_global_configuration method calls CowExportConf.run()

        This test ensures that when export_global_configuration is called,
        it creates an instance of CowExportConf with the correct configuration
        and calls its run method.
        """
        # Mock the appConfig
        mock_app_config = MagicMock()

        # Create an instance of ConfigureToolingCommand with the mock appConfig
        command = ConfigureToolingCommand(mock_app_config)

        # Mock CowExportConf
        with patch('CostMinimizer.commands.configure_tooling.CowExportConf') as mock_cow_export_conf:
            # Call the method under test
            command.export_global_configuration()

            # Assert that CowExportConf was instantiated with the correct appConfig
            mock_cow_export_conf.assert_called_once_with(command.appConfig)

            # Assert that the run method of CowExportConf was called
            mock_cow_export_conf.return_value.run.assert_called_once()

    def test_get_athena_cur_databases_1(self):
        """
        Test that get_athena_cur_databases method returns the expected terminal menu
        when Athena client successfully lists databases.
        """
        # Mock the necessary objects and methods
        mock_app_config = MagicMock()
        mock_auth_manager = MagicMock()
        mock_boto_session = MagicMock()
        mock_athena_client = MagicMock()

        mock_app_config.auth_manager = mock_auth_manager
        mock_auth_manager.aws_cow_account_boto_session = mock_boto_session
        mock_boto_session.client.return_value = mock_athena_client

        # Mock the Athena client's list_databases method
        mock_athena_client.list_databases.return_value = {
            'DatabaseList': [
                {'Name': 'database1'},
                {'Name': 'database2'},
                {'Name': 'database3'}
            ]
        }

        # Create an instance of ConfigureToolingCommand
        command = ConfigureToolingCommand(MagicMock())
        command.appConfig = mock_app_config

        # Mock the launch_terminal_menu function
        with patch('CostMinimizer.commands.configure_tooling.launch_terminal_menu') as mock_launch_menu:
            mock_launch_menu.return_value = ('selected_database', 0)

            # Call the method under test
            result = command.get_athena_cur_databases()

        # Assertions
        mock_athena_client.list_databases.assert_called_once_with(CatalogName='AwsDataCatalog')
        mock_launch_menu.assert_called_once_with(
            ['database1', 'database2', 'database3'],
            title='Select Athena CUR database:',
            subtitle='subtitle',
            multi_select=True,
            show_multi_select_hint=True,
            show_search_hint=True,
            exit_when_finished=True
        )
        assert result == ('selected_database', 0)

    def test_get_athena_cur_tables_1(self):
        """
        Test that get_athena_cur_tables correctly retrieves Athena CUR tables
        and returns the result of launch_terminal_menu.
        """
        # Mock the necessary objects and methods
        mock_app_config = MagicMock()
        mock_app_config.auth_manager.aws_cow_account_boto_session.client.return_value.list_table_metadata.return_value = {
            'TableMetadataList': [
                {'Name': 'table1'},
                {'Name': 'table2'},
                {'Name': 'table3'}
            ]
        }

        configure_tooling = ConfigureToolingCommand(MagicMock())
        configure_tooling.appConfig = mock_app_config

        with patch('CostMinimizer.commands.configure_tooling.launch_terminal_menu') as mock_launch_terminal_menu:
            mock_launch_terminal_menu.return_value = ('selected_table', 0)

            result = configure_tooling.get_athena_cur_tables('test_database')

            # Assert that list_table_metadata was called with correct parameters
            mock_app_config.auth_manager.aws_cow_account_boto_session.client.return_value.list_table_metadata.assert_called_once_with(
                CatalogName='AwsDataCatalog',
                DatabaseName='test_database'
            )

            # Assert that launch_terminal_menu was called with correct parameters
            mock_launch_terminal_menu.assert_called_once_with(
                ['table1', 'table2', 'table3'],
                title='Select Athena CUR table:',
                subtitle='subtitle',
                multi_select=True,
                show_multi_select_hint=True,
                show_search_hint=True,
                exit_when_finished=True
            )

            # Assert that the method returns the result of launch_terminal_menu
            assert result == ('selected_table', 0)

    def test_get_report_menu_items_1(self):
        """
        Test that get_report_menu_items raises SystemExit when no reports are found.
        """
        # Arrange
        mock_app_config = MagicMock()
        mock_app_config.database.get_available_reports.return_value = []
        mock_app_config.console = MagicMock()

        configure_tooling = ConfigureToolingCommand(MagicMock())
        configure_tooling.appConfig = mock_app_config

        # Act & Assert
        with pytest.raises(SystemExit):
            configure_tooling.get_report_menu_items()

        mock_app_config.console.print.assert_called_once_with("[red]Error : No reports found in the CostMinimizer database. Please check configuration file !")

    def test_get_report_menu_items_no_reports(self):
        """
        Test the behavior of get_report_menu_items when no reports are found in the database.
        This should trigger the error handling in the method and exit the program.
        """
        # Mock the necessary dependencies
        mock_appConfig = MagicMock()
        mock_database = MagicMock()
        mock_console = MagicMock()

        # Set up the mock to return an empty list of reports
        mock_database.get_available_reports.return_value = []
        mock_appConfig.database = mock_database
        mock_appConfig.console = mock_console

        # Create an instance of ConfigureToolingCommand with the mocked appConfig
        command = ConfigureToolingCommand(MagicMock())
        command.appConfig = mock_appConfig

        # Call the method and check if it exits as expected
        with pytest.raises(SystemExit):
            command.get_report_menu_items()

        # Verify that the error message was printed
        mock_console.print.assert_called_once_with("[red]Error : No reports found in the CostMinimizer database. Please check configuration file !")

    def test_insert_automated_configuration_1(self):
        """
        Test that insert_automated_configuration successfully updates the cow configuration
        when given valid configuration data.
        """
        # Arrange
        mock_app_instance = MagicMock()
        command = ConfigureToolingCommand(mock_app_instance)
        command.update_cow_configuration_record = MagicMock()

        test_configuration = {
            "aws_cow_account": "123456789012",
            "aws_cow_profile": "test_profile",
            "output_folder": "/test/output"
        }

        # Act
        command.insert_automated_configuration(test_configuration)

        # Assert
        command.update_cow_configuration_record.assert_called_once_with(test_configuration)

    def test_insert_automated_configuration_2(self):
        """
        Test that insert_automated_configuration raises ErrorInConfigureCowInsertDB
        when update_cow_configuration_record fails.
        """
        # Arrange
        mock_app_instance = MagicMock()
        command = ConfigureToolingCommand(mock_app_instance)
        command.update_cow_configuration_record = MagicMock(side_effect=Exception("Database error"))
        command.logger = MagicMock()

        test_configuration = {
            "aws_cow_account": "123456789012",
            "aws_cow_profile": "test_profile",
            "output_folder": "/test/output"
        }

        # Act & Assert
        with pytest.raises(ErrorInConfigureCowInsertDB) as exc_info:
            command.insert_automated_configuration(test_configuration)

        assert str(exc_info.value) == "ERROR: failed to insert cow configuration into database."
        command.logger.info.assert_called_once_with("ERROR: failed to insert cow configuration into database.")

    def test_menu_1(self):
        """
        Test the menu method of ConfigureToolingCommand class.

        This test verifies that the menu method correctly handles user input
        and calls the appropriate methods based on the user's selection.
        """
        # Mock the ConfigureToolingCommand instance
        mock_instance = MagicMock()

        # Mock the input function to simulate user input
        with patch('builtins.input', side_effect=['', '']):
            # Mock the launch_terminal_menu function to return predefined values
            with patch('CostMinimizer.commands.configure_tooling.launch_terminal_menu', side_effect=[
                ('Manual CostMinimizer Tool Configuration (setup my AWS account)', 0),
                ('QUIT MENU', 4)
            ]):
                # Call the menu method
                ConfigureToolingCommand.menu(mock_instance)

        # Assert that the appropriate methods were called based on user selection
        mock_instance.automated_cow_configuration.assert_called_once_with(auto=False)
        assert mock_instance.automated_cow_configuration.call_count == 1
        assert mock_instance.validate_cow_configuration.call_count == 0

    def test_menu_2(self):
        """
        Test the menu method of ConfigureToolingCommand class.

        This test verifies that the menu method correctly handles all possible
        selections (0 through 4) and calls the appropriate methods for each selection.
        It also checks that the loop breaks when selection 4 is made.

        Path constraints: 
        - The method enters the while loop (True)
        - All possible selections (0, 1, 2, 3, 4) are tested
        - The loop breaks when selection == 4
        """
        # Create a mock AppInstance
        mock_app_instance = MagicMock()

        # Create an instance of ConfigureToolingCommand
        configure_tooling = ConfigureToolingCommand(mock_app_instance)

        # Mock the methods that should be called
        configure_tooling.automated_cow_configuration = MagicMock()
        configure_tooling.automated_cow_internals_parameters = MagicMock()
        configure_tooling.validate_cow_configuration = MagicMock()
        configure_tooling.nice_display_aws_account_configured = MagicMock()

        # Mock the input function to avoid waiting for user input
        with patch('builtins.input', return_value=''):
            # Mock the launch_terminal_menu function to return different selections
            with patch('CostMinimizer.commands.configure_tooling.launch_terminal_menu') as mock_menu:
                mock_menu.side_effect = [
                    ('', 0),  # First call, select option 0
                    ('', 1),  # Second call, select option 1
                    ('', 2),  # Third call, select option 2
                    ('', 3),  # Fourth call, select option 3
                    ('', 4),  # Fifth call, select option 4 (exit)
                ]

                # Call the menu method
                configure_tooling.menu()

        # Assert that nice_display_aws_account_configured was called once at the beginning
        configure_tooling.nice_display_aws_account_configured.assert_called_once()

        # Assert that automated_cow_configuration was called twice with correct arguments
        assert configure_tooling.automated_cow_configuration.call_count == 2
        configure_tooling.automated_cow_configuration.assert_any_call(auto=False)
        configure_tooling.automated_cow_configuration.assert_any_call(auto=True)

        # Assert that automated_cow_internals_parameters was called once
        configure_tooling.automated_cow_internals_parameters.assert_called_once()

        # Assert that validate_cow_configuration was called once
        configure_tooling.validate_cow_configuration.assert_called_once()

        # Assert that launch_terminal_menu was called 5 times (4 selections + exit)
        assert mock_menu.call_count == 5

    def test_pptx_menu_1(self):
        """
        Test the pptx_menu method of ConfigureToolingCommand class.

        This test verifies that the method correctly sets up the menu items,
        title, and subtitle, and returns the expected terminal_menu result.
        """
        # Create a mock ConfigureToolingCommand instance
        command = MagicMock(spec=ConfigureToolingCommand)

        # Mock the launch_terminal_menu function
        with patch('CostMinimizer.commands.configure_tooling.launch_terminal_menu') as mock_launch_terminal_menu:
            # Set up the mock to return a specific value
            mock_launch_terminal_menu.return_value = ('Powerpoint Report: All Linked Accounts Under Payer', 0)

            # Call the method under test
            result = ConfigureToolingCommand.pptx_menu(command, 5)

            # Assert that launch_terminal_menu was called with the correct arguments
            mock_launch_terminal_menu.assert_called_once_with(
                ['Powerpoint Report: All Linked Accounts Under Payer', 'Powerpoint Report: Selected Linked Accounts(5) - (limit 200 accounts)'],
                title='PowerPoint Report Selection:',
                subtitle='Select the Powerpoint report data settings for this report',
                multi_select=False,
                show_multi_select_hint=True,
                show_search_hint=True
            )

            # Assert that the method returns the expected result
            assert result == ('Powerpoint Report: All Linked Accounts Under Payer', 0)

    def test_regions_menu_1(self):
        """
        Test that regions_menu returns a list with a single region when given selected accounts.

        This test verifies that:
        1. The method calls get_regions with the correct arguments
        2. launch_terminal_menu is called with the correct parameters
        3. The method returns a list containing only the selected region
        """
        # Setup
        mock_app_config = MagicMock()
        mock_app_config.get_regions.return_value = ['us-east-1', 'us-west-2', 'eu-west-1']

        configure_tooling = ConfigureToolingCommand(MagicMock())
        configure_tooling.appConfig = mock_app_config

        selected_accounts = ['123456789012']

        with patch('CostMinimizer.commands.configure_tooling.launch_terminal_menu') as mock_launch_menu:
            mock_launch_menu.return_value = ['us-west-2']

            # Execute
            result = configure_tooling.regions_menu(selected_accounts)

            # Assert
            mock_app_config.get_regions.assert_called_once_with(selected_accounts=selected_accounts)
            mock_launch_menu.assert_called_once_with(
                ['us-east-1', 'us-west-2', 'eu-west-1'],
                title='Select one of the region (no impact on global checks like TA, CO and CE)',
                subtitle='-',
                multi_select=False,
                show_multi_select_hint=True,
                show_search_hint=True
            )
            assert result == ['us-west-2']

    def test_report_menu_1(self):
        """
        Test that report_menu returns all reports when 'ALL' is selected,
        and adds required reports for genai recommendations when they are not in the list.
        """
        # Setup
        mock_app_instance = MagicMock()
        mock_app_instance.config_manager.appConfig.arguments_parsed.genai_recommendations = True
        configure_tooling = ConfigureToolingCommand(mock_app_instance)

        # Mock the get_report_menu_items method
        configure_tooling.get_report_menu_items = MagicMock(return_value=[
            "Name: ALL Svc: ALL Type: ALL Desc: ALL",
            "Name: Report1 Svc: Service1 Type: Type1 Desc: Description1",
            "Name: Report2 Svc: Service2 Type: Type2 Desc: Description2"
        ])

        # Mock the launch_terminal_menu function
        with patch('CostMinimizer.commands.configure_tooling.launch_terminal_menu') as mock_launch_menu:
            mock_launch_menu.return_value = [["Name: ALL Svc: ALL Type: ALL Desc: ALL"]]

            # Call the method
            result = configure_tooling.report_menu()

        # Assertions
        assert "Name: Report1 Svc: Service1 Type: Type1 Desc: Description1" in result
        assert "Name: Report2 Svc: Service2 Type: Type2 Desc: Description2" in result
        assert "Name: TOTAL /ACCOUNTS view Svc: Cost Explorer Type: ce  Desc: Montly CostExplorer Accounts Total View" in result
        assert "Name: SERVICES view Svc: Cost Explorer Type: ce Desc: Montly CostExplorer Services View" in result


    def test_report_menu_3(self):
        """
        Test the report_menu method when 'ALL' is selected, genai_recommendations is enabled,
        and SERVICES_VIEW is not in the list_options.

        This test verifies that:
        1. When 'ALL' is selected, all available reports (except the first one) are returned.
        2. When genai_recommendations is enabled, required reports are added if missing.
        3. Specifically, SERVICES_VIEW is added when it's not already in the list_options.
        """
        # Mock the ConfigureToolingCommand instance
        mock_command = MagicMock(spec=ConfigureToolingCommand)

        # Mock the get_report_menu_items method
        mock_command.get_report_menu_items.return_value = [
            "Name: ALL Svc: ALL Type: ALL Desc: ALL",
            "Name: Report1 Svc: Service1 Type: Type1 Desc: Description1",
            "Name: Report2 Svc: Service2 Type: Type2 Desc: Description2",
            "Name: TOTAL /ACCOUNTS view Svc: Cost Explorer Type: ce Desc: Monthly CostExplorer Accounts Total View"
        ]

        # Mock the launch_terminal_menu function to return 'ALL'
        with patch('CostMinimizer.commands.configure_tooling.launch_terminal_menu') as mock_launch_menu:
            mock_launch_menu.return_value = [("Name: ALL Svc: ALL Type: ALL Desc: ALL",)]

            # Set up the appConfig mock
            mock_command.appConfig = MagicMock()
            mock_command.appConfig.arguments_parsed.genai_recommendations = True

            # Call the method under test
            result = ConfigureToolingCommand.report_menu(mock_command)

        # Assert that all reports except 'ALL' are in the result
        assert "Name: Report1 Svc: Service1 Type: Type1 Desc: Description1" in result
        assert "Name: Report2 Svc: Service2 Type: Type2 Desc: Description2" in result
        assert "Name: TOTAL /ACCOUNTS view Svc: Cost Explorer Type: ce Desc: Monthly CostExplorer Accounts Total View" in result

        # Assert that SERVICES_VIEW was added to the list
        assert "Name: SERVICES view Svc: Cost Explorer Type: ce Desc: Montly CostExplorer Services View" in result

        # Assert that 'ALL' is not in the result
        assert "Name: ALL Svc: ALL Type: ALL Desc: ALL" not in result


    def test_run_1(self):
        """
        Test that the run method calls the menu method.

        This test verifies that when the run method of ConfigureToolingCommand
        is called, it invokes the menu method of the same class.
        """
        # Import necessary modules

        # Create a mock instance of ConfigureToolingCommand
        mock_command = MagicMock(spec=ConfigureToolingCommand)

        # Call the run method
        ConfigureToolingCommand.run(mock_command)

        # Assert that the menu method was called
        mock_command.menu.assert_called_once()

    def test_update_cow_configuration_record_1(self):
        """
        Test that update_cow_configuration_record correctly processes the input config
        and calls the database methods with the expected arguments.
        """
        # Setup
        mock_app_config = MagicMock()
        mock_database = MagicMock()
        mock_app_config.database = mock_database

        command = ConfigureToolingCommand(MagicMock())
        command.appConfig = mock_app_config

        test_config = {
            "aws_cow_account": "123456789012",
            "aws_cow_profile": "test_profile"
        }

        # Execute
        command.update_cow_configuration_record(test_config)

        # Assert
        mock_database.clear_table.assert_called_once_with("cow_configuration")
        mock_database.insert_record.assert_called_once_with(test_config, "cow_configuration")

