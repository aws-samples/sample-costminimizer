from CostMinimizer.commands.version import VersionCommand
from CostMinimizer.version.version import ToolingVersion
from unittest.mock import MagicMock
import pytest

class TestVersion:

    def test___init___invalid_app_instance(self):
        """
        Test the __init__ method of VersionCommand with an invalid app instance.

        This test verifies that when an invalid app instance (None) is passed to 
        the VersionCommand constructor, it raises an AttributeError due to 
        attempting to access the 'config_manager' attribute on None.
        """
        with pytest.raises(AttributeError):
            VersionCommand(None)


    def test_version_command_displays_correct_version(self):
        """
        Test that the run method of VersionCommand correctly displays the version.

        This test verifies that:
        1. The version is retrieved from the ToolingVersion class.
        2. The version is printed to the console with the correct formatting.
        """
        # Create a mock AppConfig
        mock_app_config = MagicMock()
        mock_app_config.internals = {'internals': {'version': '1.0.0'}}

        # Create a mock AppInstance
        mock_app_instance = MagicMock()
        mock_app_instance.config_manager.appConfig = mock_app_config

        # Create VersionCommand instance
        version_command = VersionCommand(mock_app_instance)

        # Run the command
        version_command.run()

        # Assert that the correct version was printed
        mock_app_config.console.print.assert_called_once_with("Version : [yellow]1.0.0")
