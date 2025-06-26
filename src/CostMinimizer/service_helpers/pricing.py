# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from typing import Optional, Dict, Any

from ..config.config import Config
from ..report_controller.region_discovery_controller import RegionDiscoveryController


class PricingQuery:
    def __init__(self, account_number, region, service_code, **term_matches):
        self.account_number = account_number
        self.appConfig = Config()
        
        # NOTE -- currently only us-east-1 region is supported with this API
        self.region = region
        self.service_code = service_code
        
        # Setup API client 
        self.client = self.appConfig.get_client('pricing')
        
        # Pre load the list of attributes for the service
        self.__service_attributes = None
        self.attr_filters = self.__convert_term_matches(term_matches)

    def __convert_term_matches(self, term_dict):
        result = []
        for (k,v) in term_dict.items():
            result.append({'Type': 'TERM_MATCH', 'Field': k, 'Value': v})
        return result
            
        # get instance price using API AWS where the parameter are instance_type, region, operating_system, tenancy
    
    
    def get_instance_price(self, 
                          instance_type: str,
                          region: str = None,
                          operating_system: str = 'Linux',
                          tenancy: str = 'Shared',
                          pre_installed_software: str = 'NA') -> Optional[Dict[str, Any]]:
        """
        Get the price for an EC2 instance type.
        
        Args:
            instance_type (str): The instance type (e.g., 't3.micro')
            region (str): AWS region (e.g., 'us-east-1'). If None, uses current region
            operating_system (str): OS type ('Linux', 'Windows', 'RHEL', etc.)
            tenancy (str): Instance tenancy ('Shared', 'Dedicated', 'Host')
            pre_installed_software (str): Pre-installed software ('NA', 'SQL Web', etc.)
            
        Returns:
            dict: Price information including on-demand and spot pricing
        """
        self.ec2_client = self.appConfig.get_client('ec2', region_name=self.appConfig.default_selected_region)

        # Get current region if not specified
        if region is None:
            region = self.ec2_client.meta.region_name
            
        # Check cache first
        cache_key = f"{instance_type}:{region}:{operating_system}:{tenancy}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]
            
        # Convert region to region description (e.g., us-east-1 to US East (N. Virginia))
        region_map = RegionDiscoveryController().region_name_mapping
        
        region_description = region_map.get(region)
        if not region_description:
            raise ValueError(f"Region mapping not found for {region}")

        try:
            # Get On-Demand pricing
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': operating_system},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_description},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': tenancy},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': pre_installed_software},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
            ]

            response = self.client.get_products(
                ServiceCode='AmazonEC2',
                Filters=filters
            )

            price_data = {
                'on_demand': None,
                'spot': None,
                'instance_type': instance_type,
                'region': region,
                'operating_system': operating_system
            }

            # Parse On-Demand price
            for price_str in response['PriceList']:
                price_details = json.loads(price_str)
                terms = price_details.get('terms', {})
                on_demand_terms = terms.get('OnDemand', {})
                
                if on_demand_terms:
                    # Get the first price dimension
                    for term_key in on_demand_terms:
                        price_dimensions = on_demand_terms[term_key]['priceDimensions']
                        for dimension in price_dimensions.values():
                            price_data['on_demand'] = {
                                'price_per_hour': float(dimension['pricePerUnit']['USD']),
                                'description': dimension['description'],
                                'unit': dimension['unit']
                            }
                            break
                        break

            # Get Spot pricing if available
            try:
                spot_response = self.ec2_client.describe_spot_price_history(
                    InstanceTypes=[instance_type],
                    ProductDescriptions=[f'{operating_system}/UNIX'],
                    MaxResults=1
                )
                
                if spot_response['SpotPriceHistory']:
                    spot_price = float(spot_response['SpotPriceHistory'][0]['SpotPrice'])
                    price_data['spot'] = {
                        'price_per_hour': spot_price,
                        'timestamp': spot_response['SpotPriceHistory'][0]['Timestamp']
                    }
            except Exception as e:
                self.logger.warning(f"Could not fetch spot pricing: {str(e)}")
                raise e

            # Cache the results
            self._price_cache[cache_key] = price_data
            return price_data

        except Exception as e:
            self.logger.warning(f"Fetching price for {instance_type}: {str(e)}")
            raise e

    def run(self, **term_matches):       
        if len(term_matches) > 0:
            filter_list = self.__convert_term_matches(term_matches)
        else:
            filter_list = self.attr_filters
        
        results = self.client.get_products(
            ServiceCode=self.service_code,
            Filters=filter_list
        )
        return results['PriceList']
