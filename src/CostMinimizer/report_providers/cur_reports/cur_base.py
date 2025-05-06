# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ...constants import __tooling_name__, __estimated_savings_caption__

import os
import sys
import logging
import pandas as pd
import boto3
import json
from typing import Optional, Dict, Any
import sqlparse

# Required to load modules from vendored su6bfolder (for clean development env)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "./vendored"))

from abc import ABC
from CostMinimizer.report_providers.report_providers import ReportBase
from pyathena.pandas.result_set import AthenaPandasResultSet

from botocore.exceptions import ClientError


#####################################################################################################################################""
class RegionConversion():

    def get_region_code(self, region_name):
        """
        Convert AWS region long name to region code
        
        Args:
            region_name (str): Long name of the region (e.g., 'Europe (Ireland)')
        Returns:
            str: Region code (e.g., 'eu-west-1') or None if not found
        """
        region_mapping = {
            'Europe (Ireland)': 'eu-west-1',
            'Europe (London)': 'eu-west-2',
            'Europe (Paris)': 'eu-west-3',
            'Europe (Stockholm)': 'eu-north-1',
            'Europe (Frankfurt)': 'eu-central-1',
            'Europe (Milan)': 'eu-south-1',
            'Europe (Spain)': 'eu-south-2',
            'Europe (Zurich)': 'eu-central-2',
            'EU (Ireland)': 'eu-west-1',
            'EU (London)': 'eu-west-2',
            'EU (Paris)': 'eu-west-3',
            'EU (Stockholm)': 'eu-north-1',
            'EU (Frankfurt)': 'eu-central-1',
            'EU (Milan)': 'eu-south-1',
            'EU (Spain)': 'eu-south-2',
            'EU (Zurich)': 'eu-central-2',
            'US East (N. Virginia)': 'us-east-1',
            'US East (Ohio)': 'us-east-2',
            'US West (N. California)': 'us-west-1',
            'US West (Oregon)': 'us-west-2',
            'Canada (Central)': 'ca-central-1',
            'South America (São Paulo)': 'sa-east-1',
            'Middle East (Bahrain)': 'me-south-1',
            'Middle East (UAE)': 'me-central-1',
            'Asia Pacific (Tokyo)': 'ap-northeast-1',
            'Asia Pacific (Seoul)': 'ap-northeast-2',
            'Asia Pacific (Singapore)': 'ap-southeast-1',
            'Asia Pacific (Sydney)': 'ap-southeast-2',
            'Asia Pacific (Mumbai)': 'ap-south-1'
        }
        
        return region_mapping.get(region_name)

    def get_region_name(self, region_code):
        """
        Convert AWS region code to region name
        
        Args:
            region_code (str): AWS region code (e.g., 'us-east-1')
            
        Returns:
            str: Region name (e.g., 'US East (N. Virginia)')
        """
        region_names = {
            # Americas
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            'ca-central-1': 'Canada (Central)',
            'sa-east-1': 'South America (São Paulo)',
            
            # Europe
            'eu-north-1': ('EU (Stockholm)', 'Europe (Stockholm)'),
            'eu-west-1': ('EU (Ireland)', 'Europe (Ireland)'),
            'eu-west-2': ('EU (London)', 'Europe (London)'),
            'eu-west-3': ('EU (Paris)', 'Europe (Paris)'),
            'eu-central-1': ('EU (Frankfurt)', 'Europe (Frankfurt)'),
            'eu-central-2': ('EU (Zurich)', 'Europe (Zurich)'),
            'eu-south-1': ('EU (Milan)', 'Europe (Milan)'),
            'eu-south-2': ('EU (Spain)', 'Europe (Spain)'),
            
            # Asia Pacific
            'ap-east-1': 'Asia Pacific (Hong Kong)',
            'ap-south-1': 'Asia Pacific (Mumbai)',
            'ap-south-2': 'Asia Pacific (Hyderabad)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-southeast-2': 'Asia Pacific (Sydney)',
            'ap-southeast-3': 'Asia Pacific (Jakarta)',
            'ap-southeast-4': 'Asia Pacific (Melbourne)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)',
            'ap-northeast-2': 'Asia Pacific (Seoul)',
            'ap-northeast-3': 'Asia Pacific (Osaka)',
            
            # Middle East
            'me-south-1': 'Middle East (Bahrain)',
            'me-central-1': 'Middle East (UAE)',
            
            # Africa
            'af-south-1': 'Africa (Cape Town)',
            
            # China
            'cn-north-1': 'China (Beijing)',
            'cn-northwest-1': 'China (Ningxia)',
            
            # AWS GovCloud
            'us-gov-east-1': 'AWS GovCloud (US-East)',
            'us-gov-west-1': 'AWS GovCloud (US-West)',
            
            # Local Zones
            'us-west-2-lax-1a': 'US West (Los Angeles)',
            'us-west-2-las-1': 'US West (Las Vegas)',
            
            # Wavelength Zones
            'us-east-1-wl1-bos-wlz-1': 'US East (Boston)',
            'us-east-1-wl1-nyc-wlz-1': 'US East (New York)',
            
            # Israel
            'il-central-1': 'Israel (Tel Aviv)'
        }
        
        return region_names.get(region_code, region_code)

#####################################################################################################################################""
class AWSSnapshots(RegionConversion):
    def __init__(self, app):
        # Price List API is only available in us-east-1 or ap-south-1
        self.ebs_client = boto3.client('ebs', region_name='us-east-1')
        self.ec2_client = boto3.client('ec2', region_name='us-east-1')

        # Cache for pricing data to avoid repeated API calls
        self._price_cache = {}
        self.database = app.database

        self.logger = logging.getLogger(__name__)

    def get_snapshot_info(self, snapshot_id, p_region):
        """
        Get the total size information for a specific EBS snapshot
        
        Args:
            snapshot_id (str): The ID of the snapshot (e.g., 'snap-0123456789abcdef0')
        Returns:
            dict: Dictionary containing size information
        """
        try:

            # define region to p_region for ec2_client
            self.ec2_client = boto3.client('ec2', region_name=self.get_region_code(p_region))
            self.ebs_client = boto3.client('ebs', region_name=self.get_region_code(p_region))

            # Get basic snapshot information
            response = self.ec2_client.describe_snapshots( SnapshotIds=[snapshot_id])
            
            if not response['Snapshots']:
                return None
                
            snapshot = response['Snapshots'][0]
            volume_size = snapshot['VolumeSize']  # Size in GiB
            
            # Initialize size information dictionary
            size_info = {
                'snapshot_id': snapshot_id,
                'volume_size_gib': volume_size,
                'volume_size_bytes': volume_size * 1024 * 1024 * 1024,  # Convert GiB to bytes
                'start_time': snapshot['StartTime'],
                'description': snapshot.get('Description', ''),
                'state': snapshot['State']
            }
            
            # Get block information using EBS direct APIs
            try:
                # List all blocks in the snapshot
                block_count = 0
                next_token = None
                
                while True:
                    if next_token:
                        blocks_response = self.ebs_client.list_snapshot_blocks(
                            SnapshotId=snapshot_id,
                            MaxResults=1000,
                            NextToken=next_token
                        )
                    else:
                        blocks_response = self.ebs_client.list_snapshot_blocks(
                            SnapshotId=snapshot_id,
                            MaxResults=1000
                        )
                    
                    # Each block is 512 KiB
                    block_count += len(blocks_response.get('Blocks', []))
                    
                    next_token = blocks_response.get('NextToken')
                    if not next_token:
                        break
                
                # Calculate actual data size (each block is 512 KiB)
                actual_size_bytes = block_count * 512 * 1024  # Convert blocks to bytes
                size_info['actual_data_size_bytes'] = actual_size_bytes
                size_info['actual_data_size_gib'] = actual_size_bytes / (1024 * 1024 * 1024)
                size_info['block_count'] = block_count
                
            except ClientError as e:
                # Handle case where EBS direct APIs might not be available
                self.logger.warning(f"Could not get detailed block information: {str(e)}")
                
            return size_info
            
        except ClientError as e:
            self.logger.warning(f"Error getting snapshot information: {str(e)}")
            return None

    def print_snapshot_size_info(self, size_info):
        """
        Print formatted snapshot size information
        """
        if not size_info:
            self.logger.warning("No snapshot information available")
            return
            
        self.logger.info("\nSnapshot Size Information:")
        self.logger.info("-" * 60)
        self.logger.info(f"Snapshot ID: {size_info['snapshot_id']}")
        self.logger.info(f"Volume Size: {size_info['volume_size_gib']:.2f} GiB")
        self.logger.info(f"Creation Date: {size_info['start_time']}")
        self.logger.info(f"State: {size_info['state']}")
        
        if 'actual_data_size_gib' in size_info:
            self.logger.info(f"Actual Data Size: {size_info['actual_data_size_gib']:.2f} GiB")
            self.logger.info(f"Block Count: {size_info['block_count']}")
            self.logger.info(f"Space Efficiency: {(size_info['actual_data_size_gib']/size_info['volume_size_gib']*100):.2f}%")
        
        if size_info['description']:
            self.logger.info(f"Description: {size_info['description']}")

#####################################################################################################################################""
class AWSPricing():
    def __init__(self, app):
        # Price List API is only available in us-east-1 or ap-south-1
        self.pricing_client = boto3.client('pricing', region_name='us-east-1')
        self.ec2_client = boto3.client('ec2', region_name='us-east-1')
        
        # Cache for pricing data to avoid repeated API calls
        self._price_cache = {}
        self.database = app.database

        self.logger = logging.getLogger(__name__)

    # function get instance price using table cow_awspricingec2 from database where the parameter are instance_type, region, operating_system, tenancy and pre_installed_software
    def get_ec2instance_price_from_db(self, instance_type, region, operating_system, tenancy, pre_installed_software):
        result = self.database.get_ec2instance_price_from_db( instance_type, region, operating_system, tenancy, pre_installed_software)

        # Check if a result is a float value
        if isinstance(result, float):
            return result
        else:
            return None

    # function get instance price using table cow_awspricingdb from database where the parameter are instance_type, region, operating_system, tenancy and pre_installed_software
    def get_dbinstance_price_from_db(self, instance_type, region, database_engine, deployment_option, pre_installed_software):
        result = self.database.get_dbinstance_price_from_db( instance_type, region, database_engine, deployment_option, pre_installed_software)

        # Check if a result is a float value
        if isinstance(result, float):
            return result
        else:
            return None

    # function get lambda price using table cow_awspricinglambda from database where the parameter are region, usagetype
    def get_lambda_price_from_db(self, region, usage_type):
        result = self.database.get_lambda_price_from_db( region, usage_type)

        # Check if a result is a float value
        if isinstance(result, float):
            return result
        else:
            return None

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
        
        # Get current region if not specified
        if region is None:
            region = self.ec2_client.meta.region_name
            
        # Check cache first
        cache_key = f"{instance_type}:{region}:{operating_system}:{tenancy}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]
            
        # Convert region to region description (e.g., us-east-1 to US East (N. Virginia))
        region_map = {
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            # Add more regions as needed
        }
        
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

            response = self.pricing_client.get_products(
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

    # get lambda price using API AWS where the parameter are instance_type, region, usage_type
    def get_lambda_price(self, region, usage_type):
        """
        Get the price for a Lambda function.

        Args:
            region (str or tuple): AWS region (e.g., 'us-east-1') or tuple of possible region names
            usage_type (str): Usage type (e.g., 'Lambda-GB-Second')

        Returns:
            dict: Price information including on-demand pricing
        """

        # Convert single region to tuple for consistent handling
        if isinstance(region, str):
            region_values = (region,)
        else:
            region_values = region

        # Create cache key from all possible region values
        cache_key = f"{'-'.join(region_values)}:{usage_type}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        try:
            # Start with the usage type filter
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'usagetype', 'Value': usage_type},
            ]

            # For location, we need to use a different approach since AWS Pricing API doesn't support OR conditions directly
            # We'll make separate API calls for each region and combine the results
            all_products = []
            
            for region_name in region_values:
                region_filter = filters + [{'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_name}]
                
                response = self.pricing_client.get_products(
                    ServiceCode='AWSLambda',
                    Filters=region_filter
                )
                
                all_products.extend(response.get('PriceList', []))
                
            # If we didn't find any products, try one more time with all filters
            if not all_products:
                response = self.pricing_client.get_products(
                    ServiceCode='AWSLambda',
                    Filters=filters
                )
                all_products = response.get('PriceList', [])
                
            # Process the combined results
            result = self._process_lambda_pricing(all_products)
            
            # Cache the result
            self._price_cache[cache_key] = result
            return result
            
        except Exception as e:
            self.logger.warning(f"Error getting Lambda price for {region_values}, {usage_type}: {e}")
            return None
            
    def _process_lambda_pricing(self, price_list):
        """
        Process Lambda pricing information from the price list.
        
        Args:
            price_list (list): List of price information from AWS Pricing API
            
        Returns:
            dict: Processed pricing information
        """
        if not price_list:
            return None
            
        # Process the pricing information
        # This is a simplified example - you may need to adjust based on your needs
        for price_str in price_list:
            try:
                price_data = json.loads(price_str)
                on_demand = price_data.get('terms', {}).get('OnDemand', {})
                if on_demand:
                    # Get the first price dimension
                    dimension_key = list(list(on_demand.values())[0]['priceDimensions'].keys())[0]
                    price_dimension = list(on_demand.values())[0]['priceDimensions'][dimension_key]
                    
                    return {
                        'pricePerUnit': price_dimension.get('pricePerUnit', {}).get('USD', '0'),
                        'description': price_dimension.get('description', ''),
                        'effectiveDate': list(on_demand.values())[0].get('effectiveDate', ''),
                        'unit': price_dimension.get('unit', '')
                    }
            except Exception as e:
                self.logger.error(f"Error processing Lambda price: {e}")
                
        return None

    def get_savings_plan_rates(self, instance_type: str, region: str = None) -> Optional[Dict]:
        """
        Get Savings Plan rates for an instance type.
        Note: This is a simplified version and actual SP rates might vary based on term and payment options.
        """
        try:
            filters = [
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region or self.ec2_client.meta.region_name},
                {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Compute Instance Savings Plan'},
            ]

            response = self.pricing_client.get_products(
                ServiceCode='AWSComputeSavingsPlans',
                Filters=filters
            )

            return response
        except Exception as e:
            self.logger.warning(f"Fetching Savings Plan rates: {str(e)}")
            return None

    def compare_instance_prices(self, 
                              instance_types: list,
                              region: str = None,
                              operating_system: str = 'Linux') -> Dict[str, Any]:
        """
        Compare prices for multiple instance types.
        
        Args:
            instance_types (list): List of instance types to compare
            region (str): AWS region
            operating_system (str): Operating system
            
        Returns:
            dict: Comparison of prices for all instance types
        """
        comparison = {}
        
        for instance_type in instance_types:
            price_data = self.get_instance_price(
                instance_type=instance_type,
                region=region,
                operating_system=operating_system
            )
            
            if price_data:
                comparison[instance_type] = price_data
                
        return comparison

#####################################################################################################################################""
class InstanceConversionToGraviton(RegionConversion):

    def __init__(self, appInstance):
        # Link to database class
        self.database = appInstance.database

    def get_graviton_equivalent(self, instance_family):
        # Remove any suffix after dot (e.g., 'search' or 'elasticsearch')
        base_family = instance_family
        
        # Mapping dictionary for instance families to their Graviton equivalents
        graviton_mapping = {
            # General Purpose (T, M series)
            't1': 't4g',
            't2': 't4g',
            't3': 't4g',
            't3a': 't4g',
            'm1': 'm6g',
            'm2': 'm6g',
            'm3': 'm6g',
            'm4': 'm6g',
            'm5': 'm6g',
            'm5a': 'm6g',
            'm5ad': 'm6gd',
            'm5d': 'm6gd',
            'm6a': 'm7g',
            'm6i': 'm7g',
            'm6id': 'm7gd',
            'm7a': 'm8g',
            'm7i': 'm8g',

            # Compute Optimized (C series)
            'c1': 'c6g',
            'c3': 'c6g',
            'c4': 'c6g',
            'c5': 'c6g',
            'c5a': 'c6g',
            'c5ad': 'c6gd',
            'c5d': 'c6gd',
            'c5n': 'c6gn',
            'c6a': 'c7g',
            'c6i': 'c7g',
            'c6id': 'c7gd',
            'c6in': 'c7gn',
            'c7a': 'c8g',
            'c7i': 'c8g',

            # Memory Optimized (R series)
            'r3': 'r6g',
            'r4': 'r6g',
            'r5': 'r6g',
            'r5a': 'r6g',
            'r5ad': 'r6gd',
            'r5d': 'r6gd',
            'r6a': 'r7g',
            'r6i': 'r7g',
            'r6id': 'r7gd',
            'r7a': 'r8g',
            'r7i': 'r8g',

            # Storage Optimized (I series)
            'i2': 'i4g',
            'i3': 'i4g',
            'i3en': 'is4gen',
            'i4i': 'i8g',

            # Database instances
            'db.m1': 'db.m6g',
            'db.m2': 'db.m6g',
            'db.m3': 'db.m6g',
            'db.m4': 'db.m6g',
            'db.m5': 'db.m6g',
            'db.m5d': 'db.m6g',
            'db.m6i': 'db.m7g',
            'db.r3': 'db.r6g',
            'db.r4': 'db.r6g',
            'db.r5': 'db.r6g',
            'db.r6i': 'db.r7g',
            'db.t1': 'db.t4g',
            'db.t2': 'db.t4g',
            'db.t3': 'db.t4g',

            # Cache instances
            'cache.m1': 'cache.m6g',
            'cache.m2': 'cache.m6g',
            'cache.m3': 'cache.m6g',
            'cache.m4': 'cache.m6g',
            'cache.m5': 'cache.m6g',
            'cache.m6': 'cache.m7g',
            'cache.r3': 'cache.r6g',
            'cache.r4': 'cache.r6g',
            'cache.r5': 'cache.r6g',
            'cache.t1': 'cache.t4g',
            'cache.t2': 'cache.t4g',
            'cache.t3': 'cache.t4g',

            # OpenSearch/Elasticsearch instances
            'c4.search': 'c6g.search',
            'c5.search': 'c6g.search',
            'm3.search': 'm6g.search',
            'm4.search': 'm6g.search',
            'm5.search': 'm6g.search',
            'r3.search': 'r6g.search',
            'r4.search': 'r6g.search',
            'r5.search': 'r6g.search',
        }

        return graviton_mapping.get(base_family)

    # get graviton equivalent from an instance type in parameter and using cow_gravitonconversion table
    def get_graviton_equivalent_from_db(self, instance_type):
        result = self.database.get_graviton_equivalent_from_db( instance_type)

        # Check if a result was found
        if result:
            return result
        else:
            return ''

    def get_latest_graviton(self, instance_family):
        """
        Get the latest available Graviton generation for a given instance family
        """
        # Remove any suffix after dot
        base_family = instance_family.split('.')[0]
        
        latest_graviton_mapping = {
            # General Purpose
            't': 't4g',  # Latest is Graviton2
            'm': 'm8g',  # Latest is Graviton4
            
            # Compute Optimized
            'c': 'c8g',  # Latest is Graviton4
            
            # Memory Optimized
            'r': 'r8g',  # Latest is Graviton4
            
            # Storage Optimized
            'i': 'i8g',  # Latest is Graviton4
            
            # Database
            'db.m': 'db.m8g',
            'db.r': 'db.r8g',
            'db.t': 'db.t4g',
            
            # Cache
            'cache.m': 'cache.m7g',
            'cache.r': 'cache.r7g',
            'cache.t': 'cache.t4g',
            
            # Search
            'm.search': 'm7g.search',
            'c.search': 'c7g.search',
            'r.search': 'r7g.search',
        }

        # Extract the base family type (e.g., 'm' from 'm5' or 'db.m' from 'db.m5')
        family_type = base_family.rstrip('123456789')
        return latest_graviton_mapping.get(family_type)

    def get_latest_graviton_from_db(self, instance_family):
        """
        Get the latest available Graviton generation for a given instance family
        """
        # Remove any suffix after dot
        base_family = instance_family.split('.')[0]
        
        latest_graviton_mapping = {
            # General Purpose
            't': 't4g',  # Latest is Graviton2
            'm': 'm8g',  # Latest is Graviton4
            
            # Compute Optimized
            'c': 'c8g',  # Latest is Graviton4
            
            # Memory Optimized
            'r': 'r8g',  # Latest is Graviton4
            
            # Storage Optimized
            'i': 'i8g',  # Latest is Graviton4
            
            # Database
            'db.m': 'db.m8g',
            'db.r': 'db.r8g',
            'db.t': 'db.t4g',
            
            # Cache
            'cache.m': 'cache.m7g',
            'cache.r': 'cache.r7g',
            'cache.t': 'cache.t4g',
            
            # Search
            'm.search': 'm7g.search',
            'c.search': 'c7g.search',
            'r.search': 'r7g.search',
        }

        # Extract the base family type (e.g., 'm' from 'm5' or 'db.m' from 'db.m5')
        family_type = base_family.rstrip('123456789')
        return latest_graviton_mapping.get(family_type)

    def get_instance_family_mapping(self, instance_type):
        """Get potential Graviton equivalent instance families"""
        # Common mapping of x86 to Graviton instance families
        graviton_mappings = {
            't3': 't4g',
            'm5': 'm6g',
            'r5': 'r6g',
            'c5': 'c6g',
            # Add more mappings as needed
        }
        
        # Extract the family from instance type (e.g., 't3' from 't3.micro')
        family = instance_type.split('.')[0]
        
        return graviton_mappings.get(family)

    def get_instance_details(self, instance_type):
        """Get instance type specifications using describe_instance_types"""
        ec2 = boto3.client('ec2', region_name='us-east-1')
        
        try:
            response = ec2.describe_instance_types(InstanceTypes=[instance_type])
            if 'InstanceTypes' in response and response['InstanceTypes']:
                return response['InstanceTypes'][0]
            return None
        except Exception as e:
            self.logger.error(f"Error getting instance details: {str(e)}")
            return None

    def compare_instances(self, current_instance, graviton_instance):
        """Compare specifications between current and Graviton instances"""
        current_specs = self.get_instance_details(current_instance)
        graviton_specs = self.get_instance_details(graviton_instance)
        
        if not current_specs or not graviton_specs:
            return None
        
        comparison = {
            'current_instance': current_instance,
            'graviton_instance': graviton_instance,
            'vcpus': {
                'current': current_specs['VCpuInfo']['DefaultVCpus'],
                'graviton': graviton_specs['VCpuInfo']['DefaultVCpus']
            },
            'memory': {
                'current': current_specs['MemoryInfo']['SizeInMiB'],
                'graviton': graviton_specs['MemoryInfo']['SizeInMiB']
            },
            'network_performance': {
                'current': current_specs['NetworkInfo']['NetworkPerformance'],
                'graviton': graviton_specs['NetworkInfo']['NetworkPerformance']
            }
        }
        
        return comparison

    def find_graviton_alternatives(self, instance_type, region, account_id):
        """Find potential Graviton alternatives for a given instance type"""
        # First try to get recommendations from Compute Optimizer
        recommendations = self.get_graviton_equivalents(instance_type, region, account_id)
        
        if recommendations:
            return recommendations
        
        # If no Compute Optimizer recommendations, use family mapping
        graviton_family = self.get_instance_family_mapping(instance_type)
        if not graviton_family:
            return None
        
        # Get the size from the original instance type
        size = instance_type.split('.')[1]
        potential_graviton = f"{graviton_family}.{size}"
        
        # Compare specifications
        comparison = self.compare_instances(instance_type, potential_graviton)
        
        return comparison


    def get_graviton_equivalents(self, instance_id, region, account_id):
        # Create clients
        compute_optimizer = boto3.client('compute-optimizer', region_name='us-east-1')
        ec2 = boto3.client('ec2', region_name='us-east-1')

        try:
            # Get instance recommendations with Graviton preference
            instance_arn = f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}"
            response = compute_optimizer.get_ec2_instance_recommendations(
                instanceArns=[instance_arn],
                accountIds=[account_id],
                recommendationPreferences={
                    'cpuVendorArchitectures': ['AWS_ARM64']  # This specifies Graviton
                }
            )

            recommendations = []
            if 'instanceRecommendations' in response:
                for rec in response['instanceRecommendations']:
                    for option in rec.get('recommendationOptions', []):
                        recommendations.append({
                            'current_instance': rec['currentInstanceType'],
                            'recommended_instance': option['instanceType'],
                            'performance_risk': option['performanceRisk'],
                            'projected_utilization': option.get('projectedUtilization', {}),
                            'savings': {
                                'estimated_monthly_savings': option.get('estimatedMonthlySavings', {}).get('value', 0),
                                'savings_opportunity': option.get('savingsOpportunity', {}).get('value', 0)
                            }
                        })
            
            return recommendations

        except Exception as e:
            self.logger.warning(f"Getting Graviton equivalents: {str(e)}")
            return None

    def get_graviton_equivalents_from_db(self, instance_id, region, account_id):
        # Create clients
        compute_optimizer = boto3.client('compute-optimizer', region_name='us-east-1')
        ec2 = boto3.client('ec2', region_name='us-east-1')

        try:
            # Get instance recommendations with Graviton preference
            instance_arn = f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}"
            response = compute_optimizer.get_ec2_instance_recommendations(
                instanceArns=[instance_arn],
                accountIds=[account_id],
                recommendationPreferences={
                    'cpuVendorArchitectures': ['AWS_ARM64']  # This specifies Graviton
                }
            )

            recommendations = []
            if 'instanceRecommendations' in response:
                for rec in response['instanceRecommendations']:
                    for option in rec.get('recommendationOptions', []):
                        recommendations.append({
                            'current_instance': rec['currentInstanceType'],
                            'recommended_instance': option['instanceType'],
                            'performance_risk': option['performanceRisk'],
                            'projected_utilization': option.get('projectedUtilization', {}),
                            'savings': {
                                'estimated_monthly_savings': option.get('estimatedMonthlySavings', {}).get('value', 0),
                                'savings_opportunity': option.get('savingsOpportunity', {}).get('value', 0)
                            }
                        })
            
            return recommendations

        except Exception as e:
            self.logger.warning(f"Getting Graviton equivalents: {str(e)}")
            return None

#####################################################################################################################################""
class CurBase(ReportBase, ABC):
    """Base class for Cost & Usage Report operations using Athena
    >>> cur_report = CurReport()
    >>> cur_report.addReport(GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"}])
    """    
    def __init__(self, appConfig):

        super().__init__( appConfig)
        self.appConfig = appConfig
        self.config = appConfig.config

        self.logger = logging.getLogger(__name__)

        self.ESTIMATED_SAVINGS_CAPTION = __estimated_savings_caption__

        self.report_dependency_list = []  #List of dependent reports. 
        self.report_result = [] # returns list of report results
        self.report_definition = [] # returns list of report definitions (columns identification for value and category)
        self.lookback_period = None
        self.fail_query = False
        self.fail_reason = None
        self.query_id = None
        self.future = None
        self.fetched_query_result = None
        self.dataframe = None #output as dataframe
        self.output = None #output as json
        self.parsed_query = None #query after all substitutions and formating
        self.dependency_data= {}

        self.cur_s3_bucket = ''
        self.cur_db = ''
        self.cur_table = ''
        self.cur_region = ''

        #Athena table name
        self.fqdb_name = ''

    @staticmethod
    def name():
        return "CUR_BASE"

    def get_caching_status(self) -> bool:
        return True

    def post_processing(self):
        pass

    def auth(self):
        """CUR report provider authentication logic"""
        # Add any specific authentication logic here if needed
        pass

    def setup(self, run_validation=False):
        """Setup instructions for CUR report type"""
        # retrieve Athena database information from customer configuration
        try:
            self.cur_s3_bucket = self.appConfig.config['cur_s3_bucket']
            self.cur_db = self.appConfig.cur_db_arguments_parsed if self.appConfig.cur_db_arguments_parsed else self.appConfig.config['cur_db']
            self.cur_table = self.appConfig.cur_table_arguments_parsed if self.appConfig.cur_table_arguments_parsed else self.appConfig.config['cur_table']
            self.cur_region = self.appConfig.config['cur_region']
        except KeyError as e:
            self.logger.error(f'MissingCurConfigurationParameterException: Missing CUR parameter in report requests: {str(e)}')
            raise

        #Athena table name
        self.cur_db = self.appConfig.cur_db_arguments_parsed if self.appConfig.cur_db_arguments_parsed else self.appConfig.config['cur_db']
        self.cur_table = self.appConfig.cur_table_arguments_parsed if self.appConfig.cur_table_arguments_parsed else self.appConfig.config['cur_table']
        self.logger.info(f'Setting {self.name()} report table_name to: {self.fqdb_name}')

        self.partition_format = self.get_partition_format()
        self.logger.info(f'Partitions format for {self.fqdb_name} is: {self.partition_format}')

        #Athena database connection
        self._cursor = self._make_cursor()

        self.logger.info(f'setting query parameters for {self.name()}')
        self.set_query_parameters() #create parameters to pass to each query

        self.TAG_VALUE_FILTER = self.config['graviton_tags_value_filter'] or ''
        self.TAG_KEY = self.config['graviton_tags']  or ''

    def run(self, report_object, additional_input_data=None):
        """Execute the CUR report"""
        # Implement the logic to run the CUR report using Athena
        pass

    def run_additional_logic_for_provider(self, report_object, additional_input_data=None) -> None:
        self.additional_input_data = additional_input_data

    def _set_report_object(self, report):
        """Set the report object for run"""
        return report(self.query_parameters, self.appConfig.auth_manager.aws_cow_account_boto_session)

    def _make_cursor(self):
        """Create an Athena cursor"""
        # Implement the logic to create an Athena cursor
        pass

    def show_columns(self) -> list:
        """Show columns in the CUR table"""
        # Implement the logic to show columns in the CUR table
        pass

    def show_partitions(self) -> list:
        """Show partitions in the CUR table"""
        # Implement the logic to show partitions in the CUR table
        pass

    def get_partition_format(self):
        """Get the partition format for the CUR table"""
        partitions = self.show_partitions()
        if not partitions:
            return None
        
        sample_partition = partitions[0]
        partition_keys = [part.split('=')[0] for part in sample_partition.split('/')]
        return '/'.join(partition_keys)

    def set_fail_query(self, reason='Query failed with an unknown reason.'):
        '''notify the cur report handler to fail the query'''
        self.fail_query = True
        self.fail_reason = reason

    def get_query_fetchall(self) -> list:
        return self.get_query_result()

    def get_report_dataframe(self, columns=None) -> AthenaPandasResultSet:
        
        if self.dataframe is None:
            #data comes from query
            self.fetched_query_result = self.get_query_fetchall()
        else:
            #data comes from cache
            self.fetched_query_result = self.dataframe

        return pd.DataFrame(self.fetched_query_result) #, columns=self.get_expected_column_headers())

    def get_query_result(self) -> AthenaPandasResultSet:
        '''return pandas object from pyathena async query'''

        try:
            result = self.report_result[0]['Data']
        except Exception as e:
            msg = f'Unable to get query result self.report_result[0]: {e}'
            self.logger.error(msg)
            self.set_fail_query(reason=msg)
            result = None
        
        return result

    def get_query_state(self):
        '''return query state'''
        result = self.get_query_result()

        if result:
            return result.state
        else:
            return 'FAILED'

    def set_query_parameters(self) -> None:
        """Set query parameters for CUR reports"""
        self.query_parameters = {
            'database': self.cur_db,
            'table': self.cur_table,
            'output_location': f'{self.cur_s3_bucket}/athena_query_results/',
            'partition_format': self.partition_format
        }

    def calculate_savings(self):
        """Calculate savings based on CUR data"""
        # This is a placeholder method. The actual implementation would depend on
        # the specific savings calculation logic required for your use case.
        query = f"""
        SELECT 
            SUM(CASE WHEN pricing_term = 'Reserved' THEN unblended_cost ELSE 0 END) as reserved_cost,
            SUM(CASE WHEN pricing_term = 'OnDemand' THEN unblended_cost ELSE 0 END) as on_demand_cost
        FROM {self.fqdb_name}
        WHERE year = '2023' AND month = '05'
        """

        result = self.fetch_data(query, None)

        if result and 'Rows' in result['ResultSet'] and len(result['ResultSet']['Rows']) > 1:
            data = result['ResultSet']['Rows'][1]['Data']
            reserved_cost = float(data[0]['VarCharValue'])
            on_demand_cost = float(data[1]['VarCharValue'])
            savings = on_demand_cost - reserved_cost
            return savings
        else:
            return 0

    def set_workbook_formatting(self) -> dict:
        # set workbook format options
        fmt = {
            'savings_format': {'num_format': '$#,##0.00'},
            'default_column_format': {'align': 'left', 'valign': 'bottom', 'text_wrap': True},
            'large_description_format': {'align': 'left', 'valign': 'bottom', 'text_wrap': True},
            'comparison_column_format': {'num_format': '$#,##0', 'bold': True, 'font_color': 'red','align': 'right', 'valign': 'right', 'text_wrap': True},
            'header_format': {'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BC', 'border': 1}
        }
        return fmt

    def generateExcel(self, writer):
        # Create a Pandas Excel writer using XlsxWriter as the engine.\
        workbook = writer.book
        workbook_format = self.set_workbook_formatting()

        for report in self.report_result:
            if report == [] or len(report['Data']) == 0:
                continue

            report['Name'] = report['Name'][:31]
            worksheet_name = report['Name']
            df = report['Data']

            # Add a new worksheet
            worksheet = workbook.add_worksheet(report['Name'])

            # Convert specific columns to numeric type before writing
            for col in self.list_cols_currency:
                try:
                    df[df.columns[col]] = pd.to_numeric(df[df.columns[col]], errors='coerce')
                except:
                    continue

            df.to_excel(writer, sheet_name=report['Name'])

            # Format workbook columns in self.list_cols_currency as money
            for col_idx in self.list_cols_currency:
                col_letter = chr(65 + col_idx + 1)
                worksheet.set_column(f"{col_letter}:{col_letter}", 30, 
                                workbook.add_format(workbook_format['savings_format']))

            if self.chart_type_of_excel == 'chart':
    
                # Create a chart object.
                chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})

                NumLines=len(report['Data'])
                chart.add_series({
                    # Cell = line:0-Col0 => estimatedMonthlySavingsAmount column header
                    'name':       [report['Name'], 0, 0],
                    # Range = [line:Col to Line:LAST_LINE-col] => currentInstanceType column values
                    'categories': [report['Name'], self.graph_range_categories_y1, self.graph_range_categories_x1, NumLines, self.graph_range_categories_x2 ],      
                    # Range = [line:Col to Line:LAST_LINE-col] => estimatedMonthlySavingsAmount column values
                    'values':     [report['Name'], self.graph_range_values_y1, self.graph_range_values_x1, NumLines, self.graph_range_values_x2],      
                })
                chart.set_y_axis({'label_position': 'low'})
                chart.set_x_axis({'label_position': 'low'})
                worksheet.insert_chart('O2', chart, {'x_scale': 2.0, 'y_scale': 2.0})

            elif self.chart_type_of_excel == 'pivot':

                # define the minimum value for the potential_savings to be displayed in the pivot graph
                self.min_savings_to_display = 0
                if report['DisplayPotentialSavings'] is True:
                    l_name_of_column = 'Potential Savings'
                else:
                    l_name_of_column = 'Total Costs'

                # Create pivot chart for potential savings by instance type
                pivot_data = (df.groupby([df.columns[i] for i in self.group_by])[df.columns[self.graph_range_values_x1]]
                              .sum()
                              .reset_index()
                              .query(f"`{df.columns[self.graph_range_values_x1]}` > {self.min_savings_to_display}")
                              .sort_values(by=df.columns[self.graph_range_values_x1], ascending=False, na_position='last'))

                if not pivot_data.empty:
                    # Create a new worksheet for the chart
                    l_name_of_worksheet = f"{worksheet_name[:31-len('-GroupBy')]}-GroupBy"
                    l_name_of_worksheet = l_name_of_worksheet[:31]
                    chart_sheet = workbook.add_worksheet(l_name_of_worksheet)

                    # Write the pivot data to the worksheet
                    index_col = 0
                    for col in self.group_by:
                        list_values = [x for x in pivot_data[df.columns[col]].values]
                        chart_sheet.write_column(f'{chr(65+index_col)}1', ['GroupBy'] + list_values)
                        index_col = index_col + 1
                    list_savings = [float(x) for x in pivot_data[df.columns[self.graph_range_values_x1]].values]
                    chart_sheet.write_column(f'{chr(65+index_col)}1', [l_name_of_column] + list_savings)

                    # Create a new chart object
                    chart = workbook.add_chart({'type': 'column'})

                    # Configure the chart
                    chart.add_series({
                        'name': l_name_of_column,
                        'categories': f'=\'{l_name_of_worksheet}\'!$A$2:${chr(65+len(self.group_by)-1)}${len(pivot_data) + 1}',
                        'values': f'=\'{l_name_of_worksheet}\'!${chr(66+len(self.group_by)-1)}$2:${chr(66+len(self.group_by)-1)}${len(pivot_data) + 1}',
                        'data_labels': {'value': True, 'num_format': '$#,##0'},
                    })

                    # Set chart title and axis labels
                    l_name_of_worksheet = f'{worksheet_name} GroupBy'
                    chart.set_title({'name': l_name_of_worksheet})
                    chart.set_x_axis({'name': 'GroupBy'})
                    chart.set_y_axis({'name': f'{l_name_of_column} ($)', 'num_format': '$#,##0'})

                    # Insert the chart into the worksheet
                    chart_sheet.insert_chart('D2', chart, {'x_scale': 2, 'y_scale': 1.5})
                    return

    def GetMinAndMaxDateFromCurTable(self, client, fqdb_name: str, payer_id: str = '', account_id: str = '', region: str = ''):
        # self.minDate and self.maxDate is empty string
        try:
            l_msg = f"Get minDate and maxDate from the CUR table {fqdb_name}, please wait..."
            self.appConfig.console.print(l_msg)

            # get minDate and maxDate from the CUR table, used for selection like 1 month records old or 15 days records old
            l_SQL = f"""SELECT 
CAST(DATE_TRUNC('month', max(distinct(bill_billing_period_start_date))) AS DATE), 
CAST(DATE_ADD('month', 1, DATE_TRUNC('month', max(distinct(bill_billing_period_start_date)))) - INTERVAL '1' DAY AS DATE) 
FROM {fqdb_name} 
GROUP BY bill_billing_period_start_date;"""
            l_SQL2 = l_SQL.replace('\n', '').replace('\t', ' ')
            l_SQL3 = sqlparse.format(l_SQL2, keyword_case='upper', reindent=False, strip_comments=True)
            cur_db = self.appConfig.cur_db_arguments_parsed if (hasattr(self.appConfig, 'cur_db_arguments_parsed') and self.appConfig.cur_db_arguments_parsed is not None) else self.appConfig.config['cur_db']
            response = self.run_athena_query(client, l_SQL3, self.appConfig.config['cur_s3_bucket'], cur_db)
            if len(response) == 0:
                self.logger.warning(f"No resources found for athena request : {l_SQL3}.")
            else:
                minDate = response[1]['Data'][0]['VarCharValue'] if 'VarCharValue' in response[1]['Data'][0] else ''
                maxDate = response[1]['Data'][1]['VarCharValue'] if 'VarCharValue' in response[1]['Data'][1] else ''
                l_msg = f"MinDate is {minDate} and MaxDate is {maxDate} "
                self.appConfig.console.print(l_msg)
                return minDate, maxDate
        except Exception as e:
            l_msg = f"Athena Query failed with state: {e} - Verify tooling CUR configuration via --configure"
            self.appConfig.console.print("\n[red]"+l_msg)
            self.logger.error(l_msg)
        return '', ''