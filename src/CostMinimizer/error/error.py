# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"
from ..constants import __tooling_name__

class Error(Exception):
    '''Base class for custom exceptions'''
    pass

'''New Error Classes start here'''
class AuthenticationError(Exception):
    def __init__(self, e, appConfig, message="Authentication Exception"):
        self.message = message
        self.e = e
        self.appConfig = appConfig
        self.appConfig.alerts['aws_cow_profile'] = None
        if 'Admin account error' in e.args[0]:
            self.message = 'An admin role name Admin (with a capital A) is required in your aws account.'
            self.appConfig.alerts['aws_cow_profile'] = self.message
        elif 'Account not found' in e.args[0]:
            self.message = 'The account number you provided does not exist in your aws account.'
            self.appConfig.alerts['aws_cow_profile'] = self.message
        elif 'expected str, bytes or os.PathLike object, not NoneType' in e.args[0]:
            self.message = 'The admin account profile is not yet configured.  Please run CostMinimizer --configure.'
            self.appConfig.alerts['aws_cow_profile'] = self.message
        elif 'No aws account' in e.args[0]:
            self.message = 'The admin account profile is not yet configured.  Please run CostMinimizer --configure.'
            self.appConfig.alerts['aws_cow_profile'] = self.message

        super().__init__(self.message)


class CurError(Exception):
    def __init__(self, e, message='Error accessing Bubblewand CUR') -> None:
        self.message=message
        self.e = e

        if 'Table not found customer_cur_data.customer_all' in e.args[0]:
            self.message = 'Table `customer_all` not found in Bubblewand. Does the customer have CUR enabled?'
        super().__init__(self.message)

class UnableToDiscoverCustomerLinkedAccounts(Exception):
    def __init__(self, e, appConfig, message="Customer Discovery Exception"):
        self.message = message
        self.e = e
        self.appConfig = appConfig
        self.message = 'Customer Discovery CUR report failed.'
        self.appConfig.alerts['aws_cow_profile'] = self.message

class UnableToGetTagsFromBubbleWand(Exception):
    def __init__(self, e, appConfig, message="Customer Discovery Exception"):
        self.message = message
        self.e = e
        self.appConfig = appConfig
        self.message = '${message} CUR report failed.'
        self.appConfig.alerts['aws_cow_profile'] = self.message

class CustomerNotFoundError(Exception):
    def __init__(self, e, appConfig, message="Customer not found"):
        self.message = message
        self.e = e
        self.appConfig = appConfig

        msg = f"{self.message}: {self.appConfig.arguments_parsed.customer}"
        print(msg)
        self.appConfig.alerts['customer_not_found'] = msg

        customers = self.appConfig.database.get_all_customers()

        if len(customers) == 0:
            print(f'You do not have any customers defined.  Please define a customer.')
        else:
            print(f'Valid customers: ')
            for customer in customers:
                print(customer.Name)

'''Legacy Error classes are below'''
class FileEncryptionOperationError(Exception):
    '''Base class for file encryption exceptions'''
    pass

class MissingSecretOrCustomerError(Error):
    '''missing secret of customer from Input'''
    pass

class EncryptionSecretMatchingError(Error):
    '''encryption secret hash does not match'''

class InvalidEncryptionSecretError(Error):
    '''encryption secret is not exactly 16 alphanum chars long'''
    def __init__(self):
        super().__init__()

    def __str__(self):
        return f'Invalid Secret. Secret should be exactly 16 characters. Alphanumeric characters only.'

class MissingEncryptionSecretInSecretsManagerError(Error):
    '''report a missing secret '''

    def __init__(self, customer):
        super().__init__()
        self.customer = customer

    def __str__(self):
        return f'No secret found for customer: {self.customer}'
