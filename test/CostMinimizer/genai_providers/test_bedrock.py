import unittest
from unittest.mock import patch, MagicMock
import json
import io

from CostMinimizer.genai_providers.bedrock import Bedrock

class TestBedrock(unittest.TestCase):
    """Test cases for the Bedrock class."""

    @patch('CostMinimizer.genai_providers.bedrock.boto3.client')
    def test_generate_response_anthropic(self, mock_boto3_client):
        """Test generate_response with Anthropic model."""
        # Mock the boto3 client and its invoke_model method
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        
        # Mock the response from invoke_model
        mock_response = {
            'body': io.BytesIO(json.dumps({'completion': 'This is a test response'}).encode())
        }
        mock_client.invoke_model.return_value = mock_response
        
        # Create a Bedrock instance with mocked Config
        with patch('CostMinimizer.genai_providers.bedrock.Config') as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.internals = {
                'internals': {
                    'genAI': {
                        'bedrock_model_id': 'anthropic.claude-v2',
                        'max_tokens': 1000,
                        'temperature': 0.5
                    }
                }
            }
            mock_config_instance.console = MagicMock()
            mock_config.return_value = mock_config_instance
            
            # Create the Bedrock instance
            bedrock = Bedrock()
            
            # Call generate_response
            response = bedrock.generate_response("What is AWS?")
            
            # Verify the response
            self.assertEqual(response, "This is a test response")
            
            # Verify invoke_model was called with the correct parameters
            mock_client.invoke_model.assert_called_once()
            call_args = mock_client.invoke_model.call_args[1]
            self.assertEqual(call_args['modelId'], 'anthropic.claude-v2')
            
            # Verify the payload structure
            payload = json.loads(call_args['body'])
            self.assertIn('prompt', payload)
            self.assertIn('What is AWS?', payload['prompt'])
            self.assertEqual(payload['max_tokens_to_sample'], 1000)
            self.assertEqual(payload['temperature'], 0.5)
    
    @patch('CostMinimizer.genai_providers.bedrock.boto3.client')
    def test_generate_response_with_file(self, mock_boto3_client):
        """Test generate_response with a file."""
        # Mock the boto3 client and its invoke_model method
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        
        # Mock the response from invoke_model
        mock_response = {
            'body': io.BytesIO(json.dumps({'completion': 'Analysis of the CSV file'}).encode())
        }
        mock_client.invoke_model.return_value = mock_response
        
        # Create a Bedrock instance with mocked Config
        with patch('CostMinimizer.genai_providers.bedrock.Config') as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.internals = {
                'internals': {
                    'genAI': {
                        'bedrock_model_id': 'anthropic.claude-v2',
                        'max_tokens': 1000,
                        'temperature': 0.5
                    }
                }
            }
            mock_config_instance.console = MagicMock()
            mock_config.return_value = mock_config_instance
            
            # Create the Bedrock instance
            bedrock = Bedrock()
            
            # Call generate_response with a mock file
            file_binary = b'mock,csv,data'
            file_format = 'csv'
            response = bedrock.generate_response("Analyze this data", file_binary, file_format)
            
            # Verify the response
            self.assertEqual(response, "Analysis of the CSV file")
            
            # Verify invoke_model was called with the correct parameters
            mock_client.invoke_model.assert_called_once()
            call_args = mock_client.invoke_model.call_args[1]
            
            # Verify the payload structure includes file context
            payload = json.loads(call_args['body'])
            self.assertIn('prompt', payload)
            self.assertIn('csv file', payload['prompt'])
            self.assertIn('Analyze this data', payload['prompt'])

    @patch('CostMinimizer.genai_providers.bedrock.boto3.client')
    def test_generate_response_error_handling(self, mock_boto3_client):
        """Test error handling in generate_response."""
        # Mock the boto3 client to raise an exception
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client
        mock_client.invoke_model.side_effect = Exception("API error")
        
        # Create a Bedrock instance with mocked Config
        with patch('CostMinimizer.genai_providers.bedrock.Config') as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.internals = {
                'internals': {
                    'genAI': {
                        'bedrock_model_id': 'anthropic.claude-v2'
                    }
                }
            }
            mock_config_instance.console = MagicMock()
            mock_config.return_value = mock_config_instance
            
            # Create the Bedrock instance
            bedrock = Bedrock()
            
            # Call generate_response
            response = bedrock.generate_response("What is AWS?")
            
            # Verify the error response
            self.assertIn("I encountered an error", response)
            self.assertIn("API error", response)
            
            # Verify an error message was printed
            mock_config_instance.console.print.assert_called_once()

if __name__ == '__main__':
    unittest.main()