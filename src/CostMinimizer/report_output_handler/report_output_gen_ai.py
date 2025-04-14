# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import io
import ast
import pandas as pd
import re
import logging


DEFAULT_gen_ai_model = 'anthropic.claude-3-5-sonnet-20240620-v1:0' # 'anthropic.claude-3-7-sonnet-20250219-v1:0' # 

class ReportOutputGenAi():
    
    dict_pattern = r'\{(?:[^{}]|\{[^{}]*\})*\}'

    def __init__(self, appConfig) -> None:
    
        self.appConfig=appConfig
        self.logger = logging.getLogger(__name__)
        self.gen_ai_model = DEFAULT_gen_ai_model
        self.domain_list = ' use this list for the technical domains:\'Compute\',\'Cost Management\',\'Database\',\'Migration and Transfer\',\'Networking & Content Delivery\',\'Savings Plans\',\'Storage\',\'Management & Governance\',\'Machine Learning\',\'Reserved Instances\',\'Analytics\',\'Application Integration\'.'
        
    
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

    def _initiate_ai_client(self, service, config, region) -> list:
        """
        Initializes the AI client for the service.
        """

        try:
            self.client = self.appConfig.auth_manager.aws_cow_account_boto_session.client( service, config=config, region_name=region)
        except Exception as e:
            msg=f'Boto client connection to bedrock-runtime ERROR. Check your credentials !'
            self.logger.info(msg)
            self.appConfig.console.print(msg)
            return None
        
        return self.client


    def _generate_ai_data_question(self, app, input_text, file_binary = None, file_format = 'xlsx', filename = f'{__tooling_name__}-report-analysis') -> list:


        # only then file_binary if the parameter is not None
        if file_binary is not None:
            messages=[{'role': 'user','content': [{'text':input_text},{'document': {'format': file_format,'name': filename, 'source': {'bytes': file_binary }}}]}]   
        else:
            messages=[{'role': 'user','content': [{'text':input_text}]}]

        #TODO: do we need to check if the model is enabled first?
        try:
            response = self.client.converse(modelId=self.gen_ai_model,messages=messages)    
        except self.client.exceptions.AccessDeniedException as e:
            msg=f'Claude 3 Sonnet model not enabled. No Bedrock recommendations created. {e}'
            self.logger.info(msg)
            self.appConfig.console.print(msg)
            return []
        except Exception as e:
            # This will catch any other unexpected exceptions
            msg = f"[red]An unexpected error occurred: {str(e)}"
            # Handle the error appropriately, perhaps by logging or raising a custom exception
            self.logger.info(msg)
            self.appConfig.console.print('\n'+msg)
            return []

        bedrock_response = []

        for message in response['output']['message']['content']:
            bedrock_response.append( message['text'])
            break

        if type(bedrock_response) is str:
            return bedrock_response
        elif type(bedrock_response) is list: 
            return bedrock_response[0]
        else:
            return []     


    def _generate_ai_data(self, app, file_binary, input_text, file_format, filename = f'{__tooling_name__}-report-analysis') -> list:
        # Increase the read timeout to 300 seconds (5 minutes)

        config = Config(
            read_timeout=300,
            connect_timeout=300
        )

        try:
            client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('bedrock-runtime', config=config, region_name='us-east-1')
        except Exception as e:
            msg=f'Boto client connection to bedrock-runtime ERROR. Check your credentials !'
            self.logger.info(msg)
            self.appConfig.console.print(msg)
            return []

        # only then file_binary if the parameter is not None
        if file_binary is not None:
            messages=[{'role': 'user','content': [{'text':input_text},{'document': {'format': file_format,'name': filename,'source': {'bytes': file_binary }}}]}]   
        else:
            messages=[{'role': 'user','content': [{'text':input_text}]}]


        #TODO: do we need to check if the model is enabled first?
        try:
            response = client.converse(modelId=self.gen_ai_model,messages=messages)    
        except client.exceptions.AccessDeniedException as e:
            msg=f'Claude 3 Sonnet model not enabled. No Bedrock recommendations created. {e}'
            self.logger.info(msg)
            self.appConfig.console.print(msg)
            return []
        except Exception as e:
            # This will catch any other unexpected exceptions
            msg = f"[red]An unexpected error occurred: {str(e)}"
            # Handle the error appropriately, perhaps by logging or raising a custom exception
            self.logger.info(msg)
            self.appConfig.console.print(msg)
            return []

        bedrock_response = []

        for message in response['output']['message']['content']:
            bedrock_response.append( message['text'])
            break

        if type(bedrock_response) is str:
            try:
                bedrock_response = ast.literal_eval(bedrock_response)
            except Exception as e:
                matches = re.findall( ReportOutputGenAi.dict_pattern, bedrock_response)
                if matches:
                    if type(matches) is list and len(matches) > 0:
                        bedrock_response = matches
                    else:
                        bedrock_response = ast.literal_eval(matches[0])
                else:
                    msg = f"Error parsing JSON: {str(e)}"
                    self.logger.info(msg)
                    self.appConfig.console.print(msg)
                    bedrock_response = None
    
        #re-run if the response comes back in a non-list format
        #if type(bedrock_response) is not list:
        #    response = client.converse(modelId=self.gen_ai_model,messages=messages)     
        #
        #    bedrock_response = []
        #
        #    for message in response['output']['message']['content']:
        #        bedrock_response = message['text']
        #
        #    bedrock_response = json.dumps(bedrock_response)
        #    bedrock_response = json.loads(bedrock_response)  

        if type(bedrock_response) is not list: 
            return []     
        else:
            return bedrock_response
    
    def _convert_file_to_base64(self,file_path):
        with open(file_path, "rb") as file:
            binary_data = file.read()
            
            return binary_data
        
    def run(self, report_file_name, prompt, file_format,encrypted = False, data_source='memory')-> list:
        #data_source should either take a 'file', 'memory' or 'dataframe' argument depending on if the source is disk(file) or memory (the rest)
        
        if data_source == 'file':
            base64_file = self._convert_file_to_base64(report_file_name)
            
        elif data_source == 'dataframe':
            io_writer = io.BytesIO()
            report_file_name.to_csv(io_writer)
            io_writer.seek(0)
            base64_file = io_writer.getvalue()
        
        else:  
            df = pd.DataFrame(report_file_name)
            io_writer = io.BytesIO()
            df.to_csv(io_writer)
            io_writer.seek(0)
            base64_file = io_writer.getvalue()
            
        #TODO this would be a good spot to dump a PII scrubbing/replacement method if needed
        bedrock_response = self._generate_ai_data(self.appConfig,base64_file, prompt, file_format)
        return bedrock_response