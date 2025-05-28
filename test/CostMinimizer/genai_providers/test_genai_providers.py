import unittest
from unittest.mock import patch, MagicMock

from CostMinimizer.genai_providers.genai_providers import GenAIProviders
from CostMinimizer.genai_providers.bedrock import Bedrock

class TestGenAIProviders(unittest.TestCase):
    """Test cases for the GenAIProviders class."""

    @patch('CostMinimizer.genai_providers.genai_providers.importlib.import_module')
    def test_import_provider_success(self, mock_import_module):
        """Test successful provider import."""
        # Mock the imported module and class
        mock_bedrock_class = MagicMock()
        mock_bedrock_instance = MagicMock()
        mock_bedrock_class.return_value = mock_bedrock_instance
        
        # Set up the mock module to return our mock class when getattr is called
        mock_module = MagicMock()
        mock_module.Bedrock = mock_bedrock_class
        mock_import_module.return_value = mock_module
        
        # Create a GenAIProviders instance with mocked Config
        with patch('CostMinimizer.genai_providers.genai_providers.Config') as mock_config:
            # Set up the mock config to return 'bedrock' as provider
            mock_config_instance = MagicMock()
            mock_config_instance.arguments_parsed.provider = 'bedrock'
            mock_config.return_value = mock_config_instance
            
            # Create the GenAIProviders instance
            provider = GenAIProviders()
            
            # Verify the provider was imported and instantiated
            mock_import_module.assert_called_once_with('..genai_providers.bedrock', package='CostMinimizer.genai_providers')
            self.assertIsNotNone(provider.provider_instance)
    
    @patch('CostMinimizer.genai_providers.genai_providers.importlib.import_module')
    def test_import_provider_failure(self, mock_import_module):
        """Test provider import failure."""
        # Make the import raise an ImportError
        mock_import_module.side_effect = ImportError("Provider not found")
        
        # Create a GenAIProviders instance with mocked Config
        with patch('CostMinimizer.genai_providers.genai_providers.Config') as mock_config:
            # Set up the mock config to return 'nonexistent_provider' as provider
            mock_config_instance = MagicMock()
            mock_config_instance.arguments_parsed.provider = 'nonexistent_provider'
            mock_config_instance.console = MagicMock()
            mock_config.return_value = mock_config_instance
            
            # Create the GenAIProviders instance
            provider = GenAIProviders()
            
            # Verify the provider was not instantiated
            self.assertIsNone(provider.provider_instance)
            # Verify an error message was printed
            mock_config_instance.console.print.assert_called_once()
    
    def test_manual_provider_import(self):
        """Test manually importing the Bedrock provider."""
        # This test verifies that we can import the Bedrock class directly
        # and that it has the expected methods
        bedrock = Bedrock()
        self.assertTrue(hasattr(bedrock, 'generate_response'))

if __name__ == '__main__':
    unittest.main()