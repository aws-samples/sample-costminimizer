
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from ..config.config import Config

REGION_NAMES = {
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'EU (Ireland)',
            'eu-west-2': 'EU (London)',
            'eu-west-3': 'EU (Paris)',
            'eu-central-1': 'EU (Frankfurt)',
            'eu-north-1': 'EU (Stockholm)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)',
            'ap-northeast-2': 'Asia Pacific (Seoul)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-southeast-2': 'Asia Pacific (Sydney)',
            'ap-south-1': 'Asia Pacific (Mumbai)',
            'sa-east-1': 'South America (São Paulo)',
            'ca-central-1': 'Canada (Central)'}

class RegionDiscoveryController:

    def __init__(self):
        self.appConfig = Config()
        self.region_name_mapping = REGION_NAMES

    def set_discovered_regions(self, excludedRegions=[]):
        '''
        This method will set the available regions based on the regions existing in the users account.

        excludedRegions: list of regions to exclude from the list of available regions
        '''
        self.discovered_regions = self.get_region_status(excludedRegions=[])
    
    def get_region_status(self, excludedRegions=[]):
        '''
        This method will return a list of regions available to the user.  The list of regions is based on the regions
        existing in the users account.

        excludedRegions: list of regions to exclude from the list of available regions
        selected_accounts: list of accounts to get regions for
        '''

        # Using ec2 client to get region names
        response = self.appConfig.get_client('ec2').describe_regions(AllRegions=True)

        regions = []
        for region in response['Regions']:
            region_code = region['RegionName']
            if region_code not in excludedRegions:
                description = REGION_NAMES.get(region_code)
                if description:
                    region['description'] = description
                else:
                    region['description'] = ''

        return response['Regions']
    
    def get_region_description(self, region_code) -> str:
        '''
        This method will return the region description for the submitted region short code
        based on the region existing in the users account. 

        region_code: region code in short form such as us-east-1
        '''
        for region in self.discovered_regions:
            if region['RegionName'] == region_code:
                return region['description']
        
    def region_opted_in(self, region_code) -> bool:
        '''
        This method will return the opt-in status for the submitted region short code
        based on the region existing in the users account.

        region_code: region code in short form such as us-east-1
        '''
        for region in self.discovered_regions:
            if region['RegionName'] == region_code:
                if region['OptInStatus'] == 'not-opted-in':
                    return False
                else:
                    return True    
                
        return False