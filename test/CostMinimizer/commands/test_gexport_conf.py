from CostMinimizer.commands.gexport_conf import ExportConfCommand
from CostMinimizer.gexport_conf.gexport_conf import CowExportConf
from unittest.mock import MagicMock, patch
import pytest

class TestGexportConf:

    def test___init___initializes_appConfig(self):
        """
        Test that the __init__ method of ExportConfCommand correctly initializes the appConfig attribute.
        """
        mock_config = {"test": "config"}
        export_command = ExportConfCommand(mock_config)
        assert export_command.appConfig == mock_config

    def test_init_with_none_appconfig(self):
        """
        Test that initializing ExportConfCommand with None as appConfig 
        does not raise an exception.
        """
        export_conf = ExportConfCommand(None)
        assert export_conf.appConfig is None

    def test_run_executes_cow_export_conf(self):
        """
        Test that the run method of ExportConfCommand creates a CowExportConf instance
        and calls its run method with the provided appConfig.
        """
        # Arrange
        mock_app_config = MagicMock()
        export_conf_command = ExportConfCommand(mock_app_config)

        with patch('CostMinimizer.commands.gexport_conf.CowExportConf') as mock_cow_export_conf:
            mock_cow_export_instance = MagicMock()
            mock_cow_export_conf.return_value = mock_cow_export_instance

            # Act
            export_conf_command.run()

            # Assert
            mock_cow_export_conf.assert_called_once_with(mock_app_config)
            mock_cow_export_instance.run.assert_called_once()
