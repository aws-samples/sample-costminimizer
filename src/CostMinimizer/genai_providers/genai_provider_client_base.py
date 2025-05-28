
import logging
import io
import pandas as pd
from abc import abstractmethod

from ..config.config import Config

class ProviderBase():
    def __init__(self, bc_config):
        self.logger = logging.getLogger(__name__)
        self.appConfig = Config()
        self.config = bc_config
        self.client_config = None
        self.client = None
    
    @abstractmethod
    def _process_reponse(self, response) -> list:
        '''each provider will need to post process the response'''
        pass

    @abstractmethod
    def execute(self, question, input_file, type_of_file, encrypted, data_source):
        '''each provider needs a way to execute the request'''
        pass

    def _convert_file_to_base64(self,file_path):
        with open(file_path, "rb") as file:
            binary_data = file.read()
            
            return binary_data

    def _convert_memory_input_to_binary(self, input_file):
        df = pd.DataFrame(input_file)
        io_writer = io.BytesIO()
        df.to_csv(io_writer)
        io_writer.seek(0)
        
        return io_writer.getvalue()  