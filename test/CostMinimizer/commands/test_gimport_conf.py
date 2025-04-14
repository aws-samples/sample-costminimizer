from CostMinimizer.commands.gimport_conf import ImportConfCommand
from CostMinimizer.gimport_conf.gimport_conf import CowImportConf
from unittest.mock import Mock, patch
import pytest

class TestGimportConf:

    def test___init___stores_app_config(self):
        """
        Test that the __init__ method correctly stores the provided appConfig
        """
        app_config = {"key": "value"}
        command = ImportConfCommand(app_config)
        assert command.appConfig == app_config


    def test_run_1(self):
        """
        Test that the run method of ImportConfCommand creates a CowImportConf instance
        and calls its run method with the provided app configuration.
        """
        mock_app_config = Mock()
        import_conf_command = ImportConfCommand(mock_app_config)

        with patch('CostMinimizer.commands.gimport_conf.CowImportConf') as mock_cow_import_conf:
            import_conf_command.run()

            mock_cow_import_conf.assert_called_once_with(mock_app_config)
            mock_cow_import_conf.return_value.run.assert_called_once()

    def test_run_no_app_config(self):
        """
        Test the run method with no app config provided.
        This tests the edge case where the ImportConfCommand is initialized without an app config.
        """
        command = ImportConfCommand(None)
        with pytest.raises(AttributeError):
            command.run()
