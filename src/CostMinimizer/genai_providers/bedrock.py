# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import json
import sys
import re
import ast
import backoff

from typing import List, Dict, Any, Optional
from botocore.config import Config as BConfig
from abc import abstractmethod

from ..constants import __tooling_name__
from .genai_provider_client_base import ProviderBase

def backoff_handler(details):
    print(
        f"Bedrock is throttling your request: backing off {details['wait']:0.1f} seconds after {details['tries']} tries."
        #f"calling {details['target']} with args {details['args']} and kwargs {details['kwargs']}"
    )

class Bedrock(ProviderBase):

    def __init__(self, bc_config):
        super().__init__(bc_config)

        if self.client_config is None:
            self.client_config = self._set_client_config()
        
        self.client = self.appConfig.auth_manager.aws_cow_account_boto_session.client(
                'bedrock-runtime', 
                config=self.client_config, 
                region_name=self.appConfig.internals['internals']['genAI']['default_provider_region']
            )
        
        
        self._throttling_exception = self.client.exceptions.ThrottlingException

        # Configure default model settings
        self.model_id = self.appConfig.internals.get('internals', {}).get('genAI', {}).get('default_genai_model', 'anthropic.claude-sonnet-4-20250514-v1:0') 
        self.max_tokens = self.appConfig.internals.get('internals', {}).get('genAI', {}).get('max_tokens', 4096)
        self.temperature = self.appConfig.internals.get('internals', {}).get('genAI', {}).get('temperature', 0.7)

    def _set_client_config(self):
        """
        Set the configuration for the Bedrock client.
        """
        
        return BConfig(
                    read_timeout=300,
                    connect_timeout=300,
                    retries={
                        'max_attempts': 5,
                        'mode': 'standard'
                    }
                )
    
    def _set_message(self, question, base64_file, type_of_file) -> list:
        if base64_file is not None:
            return [{'role': 'user','content': [{'text':question},{'document': {'format': type_of_file, 'name': f'{__tooling_name__}-report-analysis', 'source': {'bytes': base64_file }}}]}]   
        else:
            return [{'role': 'user','content': [{'text':question}]}]      
 
    def _process_reponse(self, response) -> list:
        bedrock_response = []

        for message in response['output']['message']['content']:
            list_message = self.parse_dict_list_from_text(message['text'])
            bedrock_response.append(list_message)
            break

        if type(bedrock_response) is str:
            return bedrock_response
        elif type(bedrock_response) is list: 
            return bedrock_response[0]
        else:
            return []
    
    def parse_dict_list_from_text(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """
        Discovers and parses a list of dictionaries from a string text.
        
        This function attempts multiple parsing strategies to extract a list of dictionaries
        from text that contains JSON-like structures in the format [ { ... } ].
        
        Args:
            text (str): The input text containing a list of dictionaries.
            
        Returns:
            Optional[List[Dict[str, Any]]]: The parsed list of dictionaries if successful, None otherwise.
            
        Example:
            >>> text = 'Some text before [{"key1": "value1"}, {"key2": "value2"}] and text after'
            >>> result = parse_dict_list_from_text(text)
            >>> print(result)
            [{'key1': 'value1'}, {'key2': 'value2'}]
        """
        if not text:
            return None
        
        # Try direct JSON parsing first (for clean JSON)
        try:
            # Check if the entire text is a valid JSON list
            result = json.loads(text)
            if isinstance(result, list) and all(isinstance(item, dict) for item in result):
                return result
        except json.JSONDecodeError:
            pass
        
        # Try using ast.literal_eval for Python literal structures
        try:
            # Find text that looks like a list of dictionaries using regex
            list_pattern = r'\[\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*\]'
            matches = re.findall(list_pattern, text, re.DOTALL)
            
            if matches:
                for match in matches:
                    try:
                        result = ast.literal_eval(match)
                        if isinstance(result, list) and all(isinstance(item, dict) for item in result):
                            return result
                    except (SyntaxError, ValueError):
                        continue
        except Exception:
            pass
        
        # Try more aggressive regex pattern to extract individual dictionaries
        try:
            dict_pattern = r'\{\s*"[^"]+"\s*:\s*"[^"]*"(?:\s*,\s*"[^"]+"\s*:\s*"[^"]*")*\s*\}'
            matches = re.findall(dict_pattern, text)
            
            if matches:
                result = []
                for match in matches:
                    try:
                        dict_obj = json.loads(match)
                        if isinstance(dict_obj, dict):
                            result.append(dict_obj)
                    except json.JSONDecodeError:
                        try:
                            dict_obj = ast.literal_eval(match)
                            if isinstance(dict_obj, dict):
                                result.append(dict_obj)
                        except (SyntaxError, ValueError):
                            continue
                
                if result:
                    return result
        except Exception:
            pass
        
        # If all else fails, try to find anything that looks like a dictionary
        try:
            # This pattern matches individual dictionaries with quoted keys and values
            dict_pattern = r'\{\s*(?:"[^"]+"\s*:\s*"[^"]*"(?:\s*,\s*"[^"]+"\s*:\s*"[^"]*")*)?\s*\}'
            matches = re.findall(dict_pattern, text)
            
            if matches:
                result = []
                for match in matches:
                    try:
                        # Add square brackets to make it a list for parsing
                        list_text = f"[{match}]"
                        parsed = json.loads(list_text)
                        if isinstance(parsed, list) and len(parsed) > 0:
                            result.extend(parsed)
                    except json.JSONDecodeError:
                        continue
                
                if result:
                    return result
        except Exception:
            pass
        
        return text

    @property
    def _send_request(self):
        """
        Send the request to the Bedrock model.
        """

        #implement backoff
        @backoff.on_exception(backoff.expo,
                    self._throttling_exception,
                    max_tries=5,
                    jitter=backoff.full_jitter,
                    logger=self.logger,
                    on_backoff=backoff_handler)
        def _call():
            # Try to get inference profile ARN from config
            inference_profile = self.appConfig.internals.get('internals', {}).get('genAI', {}).get('inference_profile_arn', None)
            
            # If inference profile is provided, use it
            if inference_profile:
                return self.client.converse(
                    modelId=self.model_id, 
                    messages=self.messages,
                    inferenceProfile=inference_profile
                )
            else:
                # Fall back to direct model ID for models that support on-demand throughput
                return self.client.converse(modelId=self.model_id, messages=self.messages)
        return _call

    def get_gen_ai_prompt(self, slide_name) -> str:
        prompt = ''
        if slide_name == 'recommendations':
            prompt=  'disregard previous instructions. use only the Estimated savings tab in xls. create a list of talking points for the recommendations. add an explations why each recommendation is important for cost optimization. include 3-4 sentences minimum in the recommendation if possible.  sort by easiest to hardest to implement. only categorize implemetation as easy or moderate. explain why a recommendation is easy or moderate to implement. place savings plan or reservation recommendations at the end of the list. add links to AWS documentation whenever possible. use trusted advisor documentation whenever possbile. link to AWS tools whenever possible. skip recommendations that provide a blank estimated savings, but include recommendations with $0 savings. skip recommendations that have \'trend\' in the name.  title each recommendation only by the Common Name in column B followed by a colon.  do not use column A data in the title. as an example, if the Common name is NAT Gateway Usage, the the title should be NAT Gateway Usage:. Format the response as a valid JSON list, where each element is a dictionary with the keys \"technical domain\", \"service\", and \"recommendation data\". Enclose the entire list within square brackets [ ]. Ensure each dictionary is enclosed within curly braces { } and that the keys and vaues are enclosed in double quotes. Double check that the JSON structure is properly formatted before providing the output.'   
        
        elif slide_name == 'service_trends':
            prompt = 'disregard previous instructions. analyze the csv file monthly trend data. ignore the first column. generate as many insights as you can about the monthly spend trends by service. sort the insights by total spend from highest to lowest. suggest alternate services that may be more cost effective along with an explanation for each insight if possible. do not suggest non-AWS services. use the raw numerical values in the amount column, without converting to millions, billions or any other unit. clearly indicate the technical domain. Format the response as a valid JSON list, where each element is a dictionary with the keys \"technical domain\", \"service\", and \"recommendation data\". Enclose the entire list within square brackets [ ]. Ensure each dictionary is enclosed within curly braces { } and that the keys and vaues are enclosed in double quotes. Double check that the JSON structure is properly formatted before providing the output.'   
            prompt = prompt + self.domain_list  
        
        elif slide_name == 'spend_trends':
            prompt = 'disregard previous instructions. based on the csv file, generate as many insights as you can about the data. ignore the first column. Format the response as a valid JSON list, where each element is a dictionary with the keys \"technical domain\", \"service\", and \"recommendation data\". Enclose the entire list within square brackets [ ]. Ensure each dictionary is enclosed within curly braces { } and that the keys and vaues are enclosed in double quotes. Double check that the JSON structure is properly formatted before providing the output.'
            prompt = prompt + self.domain_list 
            
        else:
            return 'no prompt found'

        return prompt
    def execute(self, question, input_file, type_of_file, encrypted = False, data_source='memory'):

        # self.appConfig, input_text = question, file_binary = base64_file, file_format = type_of_file
        if input_file:
            # Convert input files to base64
            if data_source == 'file':
                base64_file = self._convert_file_to_base64(str(input_file))
            else:  #memory
                base64_file = self._convert_memory_input_to_binary(input_file)
        else:
            base64_file = None
            type_of_file = None

        self.messages = self._set_message(question, base64_file, type_of_file)

        try:
            #send request to bedrock
            self.appConfig.console.print(f'[blue]Sending request to Bedrock model {self.model_id} model.  This may take some time...')
            response = self._send_request()
        except self.client.exceptions.AccessDeniedException as e:
            msg=f'Bedrock model {self.model_id} not enabled. No recommendations created. {e}'
            self.logger.info(msg)
            self.appConfig.console.print(msg)
            sys.exit()
        except Exception as e:
            # This will catch any other unexpected exceptions
            msg = f"[red]{str(e)}"
            # Handle the error appropriately, perhaps by logging or raising a custom exception
            self.logger.info(msg)
            self.appConfig.console.print(msg)
            if "ThrottlingException" in str(e):
                msg = f"[blue]See: https://docs.aws.amazon.com/bedrock/latest/userguide/quotas.html"
                self.appConfig.console.print(msg)
                return
            sys.exit()
        
        return self._process_reponse(response)
        
    