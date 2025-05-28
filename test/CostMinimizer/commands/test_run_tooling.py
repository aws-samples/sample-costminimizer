# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from argparse import Namespace

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from CostMinimizer.commands.run_tooling import RunToolingRun

class TestRunTooling(unittest.TestCase):
    """Test cases for the RunToolingRun class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock app instance
        self.mock_app = MagicMock()
        self.mock_app.config_manager.appConfig.arguments_parsed = Namespace()
        self.mock_app.config_manager.appConfig.logger = MagicMock()
        
        # Create RunToolingRun instance with mock app
        self.run_tooling = RunToolingRun(self.mock_app)
        
        # Mock logger
        self.run_tooling.logger = MagicMock()

    def test_display_regions_menu_with_region_arg(self):
        """Test display_regions_menu when region is specified via command line."""
        # Set up test data
        self.mock_app.config_manager.appConfig.arguments_parsed.region = "us-west-2"
        self.mock_app.config_manager.appConfig.arguments_parsed.co = False
        self.mock_app.config_manager.appConfig.arguments_parsed.cur = False
        
        # Call the method
        result = self.run_tooling.display_regions_menu([], [])
        
        # Assert the result
        self.assertEqual(result, ["us-west-2"])
        self.run_tooling.logger.info.assert_called_with("Using region specified via command line: us-west-2")

    def test_display_regions_menu_with_co_option(self):
        """Test display_regions_menu when --co option is used."""
        # Set up test data
        self.mock_app.config_manager.appConfig.arguments_parsed.region = None
        self.mock_app.config_manager.appConfig.arguments_parsed.co = True
        self.mock_app.config_manager.appConfig.arguments_parsed.cur = False
        
        # Mock the regions_menu method to return a list of regions
        mock_regions_menu = MagicMock(return_value=["us-east-1: Region 1", "us-west-2: Region 2"])
        self.run_tooling.appInstance.ConfigureToolingCommand().regions_menu = mock_regions_menu
        
        # Patch the ConfigureToolingCommand class
        with patch('CostMinimizer.commands.run_tooling.ConfigureToolingCommand', return_value=MagicMock()) as mock_config:
            mock_config.return_value.regions_menu.return_value = ["us-east-1: Region 1", "us-west-2: Region 2"]
            
            # Call the method
            result = self.run_tooling.display_regions_menu([], [])
            
            # Assert the result
            self.assertEqual(result, ["us-east-1", "us-west-2"])
            self.run_tooling.logger.info.assert_any_call("Displaying region selection menu for --co or --cur options")

    def test_display_regions_menu_with_cur_option(self):
        """Test display_regions_menu when --cur option is used."""
        # Set up test data
        self.mock_app.config_manager.appConfig.arguments_parsed.region = None
        self.mock_app.config_manager.appConfig.arguments_parsed.co = False
        self.mock_app.config_manager.appConfig.arguments_parsed.cur = True
        
        # Mock the regions_menu method to return a list of regions
        mock_regions_menu = MagicMock(return_value=["us-east-1: Region 1", "us-west-2: Region 2"])
        self.run_tooling.appInstance.ConfigureToolingCommand().regions_menu = mock_regions_menu
        
        # Patch the ConfigureToolingCommand class
        with patch('CostMinimizer.commands.run_tooling.ConfigureToolingCommand', return_value=MagicMock()) as mock_config:
            mock_config.return_value.regions_menu.return_value = ["us-east-1: Region 1", "us-west-2: Region 2"]
            
            # Call the method
            result = self.run_tooling.display_regions_menu([], [])
            
            # Assert the result
            self.assertEqual(result, ["us-east-1", "us-west-2"])
            self.run_tooling.logger.info.assert_any_call("Displaying region selection menu for --co or --cur options")

    def test_display_regions_menu_with_ce_option(self):
        """Test display_regions_menu when --ce option is used."""
        # Set up test data
        self.mock_app.config_manager.appConfig.arguments_parsed.region = None
        self.mock_app.config_manager.appConfig.arguments_parsed.co = False
        self.mock_app.config_manager.appConfig.arguments_parsed.cur = False
        self.mock_app.config_manager.appConfig.arguments_parsed.ce = True
        
        # Call the method
        result = self.run_tooling.display_regions_menu([], [])
        
        # Assert the result
        self.assertEqual(result, ["us-east-1"])
        self.run_tooling.logger.info.assert_called_with("Region selection skipped: neither --co nor --cur options were used")

    def test_display_regions_menu_with_ta_option(self):
        """Test display_regions_menu when --ta option is used."""
        # Set up test data
        self.mock_app.config_manager.appConfig.arguments_parsed.region = None
        self.mock_app.config_manager.appConfig.arguments_parsed.co = False
        self.mock_app.config_manager.appConfig.arguments_parsed.cur = False
        self.mock_app.config_manager.appConfig.arguments_parsed.ta = True
        
        # Call the method
        result = self.run_tooling.display_regions_menu([], [])
        
        # Assert the result
        self.assertEqual(result, ["us-east-1"])
        self.run_tooling.logger.info.assert_called_with("Region selection skipped: neither --co nor --cur options were used")

    def test_display_regions_menu_with_both_co_and_cur_options(self):
        """Test display_regions_menu when both --co and --cur options are used."""
        # Set up test data
        self.mock_app.config_manager.appConfig.arguments_parsed.region = None
        self.mock_app.config_manager.appConfig.arguments_parsed.co = True
        self.mock_app.config_manager.appConfig.arguments_parsed.cur = True
        
        # Mock the regions_menu method to return a list of regions
        mock_regions_menu = MagicMock(return_value=["us-east-1: Region 1", "us-west-2: Region 2"])
        self.run_tooling.appInstance.ConfigureToolingCommand().regions_menu = mock_regions_menu
        
        # Patch the ConfigureToolingCommand class
        with patch('CostMinimizer.commands.run_tooling.ConfigureToolingCommand', return_value=MagicMock()) as mock_config:
            mock_config.return_value.regions_menu.return_value = ["us-east-1: Region 1", "us-west-2: Region 2"]
            
            # Call the method
            result = self.run_tooling.display_regions_menu([], [])
            
            # Assert the result
            self.assertEqual(result, ["us-east-1", "us-west-2"])
            self.run_tooling.logger.info.assert_any_call("Displaying region selection menu for --co or --cur options")

if __name__ == '__main__':
    unittest.main()