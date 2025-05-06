#imports
import os
import logging
#specific imports
from pathlib import Path
#application imports
from ..config.config import Config
from ..config.database import ToolingDatabase

class ConfigurationManager:
    """Manages application configuration and setup"""
    def __init__(self):
        self._setup_configs() #instantiate Config class and run setup method
        self._setup_logging()
        self._setup_database()

    def _setup_logging(self) -> None:
        log_config = self.appConfig.internals['internals']['logging']
        log_file_path = self.appConfig.report_directory / log_config['log_file']

        self._cleanup_log_file(log_file_path)
        logging.basicConfig(
            filename=log_file_path.resolve(),
            format=log_config['log_format'],
            level=log_config['log_level_default'],
            force=True
        )

    def _cleanup_log_file(self, log_file_path: Path) -> None:
        if log_file_path.is_file():
            try:
                os.remove(log_file_path.resolve()) #
            except FileNotFoundError as r:
                self.appConfig.logger.info(f"Failed to remove log file: {r}")
            except:
                raise

    def _setup_configs(self) -> None:
        self.appConfig = Config()
        self.appConfig.setup()

    #TODO database init should probably not happen in the configuration manager
    def _setup_database(self) -> None:
        self.appConfig.database = ToolingDatabase()

        # in case the API interfaces are not accessible to get the ec2 instances prices 
        self.appConfig.database.insert_awspricingec2()

        # in case the API interfaces are not accessible to get the db instances prices 
        self.appConfig.database.insert_awspricingdb()

        # in case the API interfaces are not accessible to get the lambda instances prices 
        self.appConfig.database.insert_awspricinglambda()

        # in case the API interfaces are not accessible to get the gravition instances equivalence 
        self.appConfig.database.insert_gravitonconversion()