


import importlib

from typing import Any
from botocore.config import Config as bc_config

from ..config.config import Config

class GenAIProviders():

    def __init__(self):
        self.appConfig = Config()
        self.provider_instance = None
        self._setup_botocore_config()
        
        provider = self._provider()
        if provider:
            self.provider = self._import_provider(provider)

    def _setup_botocore_config(self) -> None:
        self.bc_config = bc_config()
        self.bc_config.read_timeout=300
        self.bc_config.connect_timeout=300
    
    def _provider(self):
        '''determine genai provider'''

        try:
            provider = self.appConfig.arguments_parsed.provider
        except:
            try:
                provider = self.appConfig.internals['internals']['genAI']['default_provider']
            except:
                provider = None
        
        return provider

    def _import_provider(self, provider: str):
        '''import provider from arguments or configuration'''
        try:
            # Dynamically import the provider module
            module_path = f"..genai_providers.{provider}"
            provider_module = importlib.import_module(module_path, package=__package__)
            
            # Get the provider class (assuming the class name is capitalized)
            provider_class_name = provider.capitalize()
            provider_class = getattr(provider_module, provider_class_name)
            
            # Instantiate the provider class
            return provider_class(self.bc_config)
        except (ImportError, AttributeError) as e:
            self.appConfig.console.print(f"[red]Error importing provider '{provider}': {str(e)}[/red]")
            return None
        except Exception as e:
            self.appConfig.console.print(f"[red]Unexpected error when importing provider '{provider}': {str(e)}[/red]")
            return None
