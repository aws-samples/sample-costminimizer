# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import boto3

from ..constants import __tooling_name__
from ..error.error import UnableToDiscoverCustomerLinkedAccounts
from rich.progress import track

class AccountDiscoveryController:
    '''retrive metadata from requested accounts'''
    def __init__(self):
        from ..config.config import Config
        self.appConfig = Config()
        self.payer_account_id = None
        self.number_of_linked_accounts = None
        self.accounts_metadata = None
        self.is_payer = self.determine_is_payer_account()

    def account_discovery_controller_setup(self):
        '''determine if discovery is enabled'''
        

        if self.is_payer:
            #payer account
            self.payer_account_id = self.get_account_id()
            self.number_of_linked_accounts = self.get_number_linked_accounts()

            if self.number_of_linked_accounts > 0:
                self.accounts_metadata = self.get_linked_accounts()

                # show progress bar based on evolution of self.accounts_metadate
                display_msg = f'[green]Running accounts discovery in regions[/green]'
                for a in track(self.accounts_metadata, description=display_msg):
                    account = a['Id']

                    try:
                        if account == self.payer_account_id:
                            session = self.appConfig.auth_manager.aws_cow_account_boto_session
                        else:
                            session = self.assume_role(self.get_organizations_role_arn(account), session_name=f'{account}-session')
                    except Exception as e:
                        self.appConfig.logger.error(f'Unable to assume role for {account} - {e}')
                        a['support_status'] = 'unknown'
                        continue

                    support_status = self.get_support_status_of_account(session=session)
                    a['support_status'] = support_status
        else:
            #standalone account
            self.accounts_metadata = []

            account_record = {'Id': self.get_account_id(), 'Email': 'unknown', 'support_status': self.get_support_status_of_account()}

            self.accounts_metadata.append(account_record)
    
    def determine_is_payer_account(self) -> bool:
        try:
            org_client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('organizations')
            # Check if the account is a master/management account
            account_details = org_client.describe_organization()

            # A payer account is typically the management account in AWS Organizations
            is_payer = account_details['Organization']['MasterAccountId'] == self.appConfig.auth_manager.aws_cow_account_boto_session.client('sts').get_caller_identity()['Account']

            return is_payer
        except Exception as e:
            if 'AWSOrganizationsNotInUseException' in str(e):
                # If the account is not part of an organization, treat it as a standalone account
                self.appConfig.logger.info("Account is not part of an AWS Organization - treating as standalone account")
                return False
            else:
                # Re-raise any other exceptions
                raise
    
    def get_account_id(self, session=None) -> str:
        '''get account id'''
        if not session:
            session = self.appConfig.auth_manager.aws_cow_account_boto_session

        sts_client = session.client('sts')
        account_id = sts_client.get_caller_identity()['Account']

        return account_id
    
    def get_number_linked_accounts(self) -> int:
        try:
            org_client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('organizations')
            # List accounts in the organization
            response = org_client.list_accounts()

            try:
                return len(response['Accounts'])
            except:
                return 0
        except Exception as e:
            if 'AWSOrganizationsNotInUseException' in str(e):
                # If the account is not part of an organization, there are no linked accounts
                return 0
            else:
                # Re-raise any other exceptions
                raise
        
    def get_linked_accounts(self) -> list:
        '''get linked accounts from organizations'''
        try:
            org_client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('organizations')
            # List accounts in the organization
            response = org_client.list_accounts()

            try:
                return response['Accounts']
            except:
                raise UnableToDiscoverCustomerLinkedAccounts(Exception, self.appConfig, 'Unable to discover linked accounts')
        except Exception as e:
            if 'AWSOrganizationsNotInUseException' in str(e):
                # If the account is not part of an organization, return an empty list
                return []
            else:
                # Re-raise any other exceptions
                raise
         
    def get_support_status_of_account(self, session=None) -> list:
        '''get support status of linked accounts'''
        
        def get_status(session):
            # Get the account ID
            if not session:
                session = self.appConfig.auth_manager.aws_cow_account_boto_session

            # Get the support status of the account
            support_client = session.client('support')

            # Get severity levels
            try:
                response = support_client.describe_severity_levels()
                severity_levels = [level['name'].lower() for level in response['severityLevels']]

                # Determine plan based on available severity levels and their response times
                if 'critical' in severity_levels:
                    return 'Enterprise'
                elif 'urgent' in severity_levels:
                    # Check if this is Business or Enterprise On-Ramp
                    # Get the code for urgent cases which contains the response time
                    for level in response['severityLevels']:
                        if level['name'].lower() == 'urgent':
                            # Enterprise On-Ramp has 4hr response time for urgent
                            if '4' in level.get('code', ''):
                                return 'Enterprise On-Ramp'
                            # Business has 1hr response time for urgent
                            else:
                                return 'Business'
                    return 'Business'  # Default if we can't determine from code
                else:
                    return 'Developer'
            except Exception as e:
                # If we can't access the Support API, it's likely Basic Support
                if 'SubscriptionRequiredException' in str(e):
                    return 'Basic'
                else:
                    raise e
        
        if self.is_payer:
            for account in self.get_linked_accounts():
                return get_status(session)
        else:
            return get_status(session)

    def get_organizations_role_arn(self, linked_account):
        organizations_role_arn = f'arn:aws:iam::{linked_account}:role/OrganizationAccountAccessRole'
        return organizations_role_arn
    
    def assume_role(self, role_arn, session_name=None, external_id=None):
        
        sts_client = self.appConfig.auth_manager.aws_cow_account_boto_session.client('sts')

        if not session_name:
            session_name = f'{__tooling_name__}-session'

        assume_role_kwargs = {
            'RoleArn': role_arn,
            'RoleSessionName': session_name
        }
    
        if external_id:
            assume_role_kwargs['ExternalId'] = external_id

        response = sts_client.assume_role(**assume_role_kwargs)

        credentials = response['Credentials']

        return boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
