# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import datetime
from Crypto.Cipher import AES
from botocore.exceptions import ClientError
import json
import os
import shutil
import sys
import hashlib
import click
from pathlib import Path
from ..error.error import FileEncryptionOperationError


class CowEncryption:

    def __init__(self, appConfig, session):
        self.appConfig = appConfig
        self.config = appConfig.config
        self.logger = appConfig.logger
        self.session = session
        self.encryption_secret = None
        self.user_secret = None
        self.hashed_user_secret = None
        self.region_name = "us-east-1"
        self.validated = False
        self.get_secret_value_response = None
        self.salt = 'd11h1zZNdyJZchKsmOa7Yzl1tboAS7fydWV2zEYHj9LgC2pR0k32MglmE2WZGB4c'

    def get_user_secret(self) -> None:
        self.user_secret = click.prompt('Please enter your encryption secret', hide_input=True, confirmation_prompt=False)

    def build_secrets_manager_client(self) -> None:
        try:
            client = self.session.client(service_name='secretsmanager',region_name=self.region_name)
        except Exception as e:
            self.logger.error(f'Unable to build the Secrets Manager client: {e}')
            if self.appConfig.mode == 'cli':
                print(f'Unable to build the Secrets Manager client: {e}')
                sys.exit(1)
            else:
                self.appConfig.alerts['missing_secret'] = f'Unable to build the Secrets Manager client'
                raise

        return client
    
    def hash_secret(self, user_secret=None) -> str:
        '''
        Return the first 16 chars of the hash of the user_secret
        '''
        if user_secret:
            secret = user_secret
        else:
            secret = self.user_secret
        hashed_secret = hashlib.md5(secret.encode()).hexdigest()
        trimmed_hashed_secret = hashed_secret[:16]

        return trimmed_hashed_secret

    def set_encryption_secret(self, user_secret=None) -> None:
        return None

    def get_hashed_secret(self, secret):
        hash_object = hashlib.md5(bytes(secret,'utf-8'))
        return hash_object.hexdigest()

    def get_aws_cow_account_secret(self, refresh=False) -> None:
        '''
        Set self.encryption secret pulled down from the AWS account. 
        Authentication is provided prior by midway.
        '''
        
        self.secrets_manager_secret_name = self.appConfig.database.get_secrets_manager_name()
       
        client = self.build_secrets_manager_client()

        try:
            if self.get_secret_value_response is None or refresh:
                self.get_secret_value_response = client.get_secret_value(SecretId=self.secrets_manager_secret_name)
                
                try:                   
                    self.encryption_secret = json.loads(self.get_secret_value_response['SecretString'])[self.secrets_manager_secret_name]
                    self.secret_age = self.get_secret_value_response['CreatedDate']
                    self.check_secret_age(self.secret_age)
                except KeyError as e:
                    if self.appConfig.mode == 'cli':
                        print(f'Unable to find secret.  Please run --configure to define a secret.')
                        sys.exit(0)
                    else:
                        self.appConfig.alerts['missing_secret'] = f"Unable to find secret: secrets_manager_secret_name.  Please check CostMinimizer configuration."
                except Exception as e:
                    if self.appConfig.mode == 'cli':
                        print(f'Unable to find a session to use for obtaining your secret: secrets_manager_secret_name.  Make sure your mwinit token is fresh or run --configure to define an admin account.')
                        sys.exit(0)
                    else:
                        self.appConfig.alerts['missing_secret'] = f"Unable to find a session to use for obtaining your secret: secrets_manager_secret_name.   Make sure your mwinit token is fresh or run --configure to define an admin account."     

        except ClientError as e:
            if e.response['Error']['Code'] in ('ResourceNotFoundException', 'InvalidRequestException'):
                if self.appConfig.mode == 'cli':
                    print(f'Unable to find secret: secrets_manager_secret_name.  Please run --configure to define a secret.')
                    sys.exit(0)
                else:
                    self.appConfig.alerts['missing_secret'] = f"Unable to find secret: secrets_manager_secret_name.  Please check CostMinimizer configuration."
        except Exception as e:
            if self.appConfig.mode == 'cli':
                print(f'Unable to find a session to use for obtaining your secret: secrets_manager_secret_name.  Make sure your mwinit token is fresh or run --configure to define an admin account.')
                sys.exit(0)
            else:
                self.appConfig.alerts['missing_secret'] = f"Unable to find a session to use for obtaining your secret: secrets_manager_secret_name.   Make sure your mwinit token is fresh or run --configure to define an admin account."
            
        self.validated = True   

    def validate_aws_cow_account_secret(self, get_secret_value_response, user_secret) -> bool:
        try:
            stored_secret = json.loads(get_secret_value_response['SecretString'])[self.secrets_manager_secret_name]
            self.hash_secret(user_secret)
            return stored_secret == self.set_encryption_secret(user_secret)
        except (KeyError, json.JSONDecodeError):
            self.logger.error("Invalid secret format or missing key in the secret")
            return False
        except Exception as e:
            self.logger.error(f"Error validating secret: {str(e)}")
            return False

    def update_aws_cow_account_secret(self, user_secret, update=False) -> None:

        self.secrets_manager_secret_name = self.appConfig.database.get_secrets_manager_name()

        client = self.build_secrets_manager_client()

        secret_string = {}
        secret_string[self.secrets_manager_secret_name]=self.set_encryption_secret(user_secret)

        if update:
            client.update_secret(SecretId = self.secrets_manager_secret_name, SecretString=json.dumps(secret_string))
        else:
            client.create_secret(Name = self.secrets_manager_secret_name, SecretString=json.dumps(secret_string))

        self.encryption_secret = self.set_encryption_secret(user_secret)
        self.hashed_user_secret = self.hash_secret(user_secret)
        self.user_secret = user_secret

    def encrypt_string(self, encryption_secret, decrypted_string) -> None:
        return None

    def decrypt_string(self, encryption_secret, encrypted_string) -> None:
        return None

    def file_write_operation(self, operation, file_to_write, data=None, cipher=None, tag=None, ciphertext=None) -> None:

        output_file = open(str(file_to_write),'wb')

        try:
            if operation == 'encrypt':
                [ output_file.write(x) for x in (cipher.nonce, tag, ciphertext) ]
                if not output_file.closed:
                    output_file.close()
            elif operation == 'decrypt':
                output_file.write(data)
        except:
            self.logger.info(f'Unable to write to file: {file_to_write} during {operation} operation.')
            raise FileEncryptionOperationError(f'Unable to write to file: {file_to_write} during {operation} operation.')
        finally:
            if not output_file.closed:
                output_file.close()

    def safe_rename(self, src, dest):
        '''
        Rename a file, but only if the destination does not exist.
        Needed on Windows
        '''
        if os.path.exists(dest):
            shutil.move(src, dest)
        else:
            os.rename(src, dest)

    def file_rename_operation(self, operation, file_to_rename:Path) -> None:

        if operation == 'encrypt':
            string_to_replace = '_decrypted'
            string_to_add = '_encrypted'
        elif operation == 'decrypt':
            string_to_replace = '_encrypted'
            string_to_add = '_decrypted'

        if isinstance(file_to_rename, Path):
                old_file_name = str(file_to_rename)
                if string_to_replace in old_file_name:
                    new_file_name = old_file_name.replace(string_to_replace, string_to_add)
                elif string_to_add in old_file_name:
                    new_file_name=old_file_name
                else:
                    new_file_name = str(file_to_rename.parent) + '/' + file_to_rename.stem + string_to_add + file_to_rename.suffix

                try:
                    self.safe_rename(old_file_name, new_file_name)
                except FileExistsError as e:
                    print(f"Error: {e}")
                except Exception as e:
                    print(f"An error occurred: {e}")

    def encrypt_file(self, file_to_encrypt:Path, rename=False) -> None:

        successful_operation = False

        try:
            with open(file_to_encrypt, "rb") as f:
                data = f.read()
            key = bytes(self.encryption_secret,'utf-8')

            cipher = AES.new(key, AES.MODE_GCM)
            nonce = cipher.nonce
            ciphertext, tag = cipher.encrypt_and_digest(data)
        except IOError as e:
            self.logger.info(f'Unable to read file: {file_to_encrypt}.')
            raise FileEncryptionOperationError(f'Unable to read file: {file_to_encrypt}.')
        except ValueError:
            self.logger.info('Encryption error occurred.')
            raise FileEncryptionOperationError('Encryption error occurred.')
        except Exception:
            self.logger.info('Unexpected error during file encryption.')
            raise FileEncryptionOperationError('Unexpected error during file encryption.')

        self.file_write_operation('encrypt', file_to_encrypt, data=None, cipher=cipher, tag=tag, ciphertext=ciphertext)

        successful_operation = True

        if rename and successful_operation:
            self.file_rename_operation('encrypt', file_to_encrypt)

    def decrypt_file(self, file_to_decrypt:Path, rename=False) -> None:

        successful_operation = False

        try:
            f = open(file_to_decrypt, "rb")
            nonce, tag, ciphertext = [ f.read(x) for x in (16, 16, -1) ]
            f.close()

            key = bytes(self.encryption_secret,'utf-8')

            cipher = AES.new(key, AES.MODE_EAX, nonce=token_bytes(16))
            data = cipher.decrypt(ciphertext)
            cipher.verify(tag)
        except ValueError as e:
            if str(e) == 'MAC check failed':
                self.logger.info(f'Unable to decrypt file: {file_to_decrypt}.  Your encryption secret may have changed or be missing.')
                if self.appConfig.mode == 'cli':
                    raise FileEncryptionOperationError(f'Unable to decrypt file: {file_to_decrypt}. The encryption secret used to encrypt this file may have change or may be missing.')
                else:
                    self.appConfig.alerts['missing_secret'] = f'Unable to decrypt file: {file_to_decrypt}. The encryption secret used to encrypt this file may have change or may be missing.'  
                    raise FileEncryptionOperationError(f'Unable to decrypt file: {file_to_decrypt}. The encryption secret used to encrypt this file may have change or may be missing.')  
        except:
            raise
            # self.logger.info(f'Unable to encrypt file: {file_to_decrypt}.')
            # raise FileEncryptionOperationError(f'Unable to encrypt file: {file_to_decrypt}')
        finally:
            if not f.closed:
                f.close()

        self.file_write_operation('decrypt', file_to_decrypt, data=data)

        successful_operation = True

        if rename and successful_operation:
            self.file_rename_operation('decrypt', file_to_decrypt)

    def encrypt_directory(self, directory_name:Path) -> None:
        '''Encrypts all files in a directory'''
        '''directory_name required to be absolute path as Path object'''
        for root, _, files in os.walk(directory_name):
            for file in files:
                file_path = os.path.join(root, file)

                if '_decrypted' in file:
                    try:
                        self.encrypt_file(Path(file_path), rename=True)
                    except (IOError, OSError) as e:
                        self.logger.error(f"Error encrypting file {file_path}: {str(e)}")

    def decrypt_directory(self, directory_name:Path) -> None:
        '''Decrypts all files in a directory'''
        '''directory_name required to be absolute path as Path object'''
        for root, _, files in os.walk(directory_name):
            for file in files:
                file_path = os.path.join(root, file)

                if '_encrypted' in file:
                    try:
                        self.decrypt_file(Path(file_path), rename=True)
                    except (IOError, OSError) as e:
                        self.logger.error(f"Error decrypting file {file_path}: {str(e)}")

    def hash_list_md5(self, list_to_hash:list) -> str:
        #sort the list and hash it
        list_to_hash.sort()
        return hashlib.md5(str(list_to_hash).encode('utf-8')).hexdigest()

    def check_secret_age(self, created_date) -> bool:

        '''check_date should be replaced with a naive datetime of the production push date''' 
        check_date = datetime.datetime.fromisoformat('2024-05-31 00:00:00.000000')
        '''check_date should be replaced with a naive datetime of the production push date'''

        if created_date.replace(tzinfo=None) < check_date:
  
            if self.prompt_to_change_secret():
                return True
            else:
                click.echo('Exiting...')
                sys.exit(1)
        else:
            return True

    def prompt_to_change_secret(self, message='New Encryption Secret Required. Please choose a new secret' ) -> bool:

        if self.appConfig.mode == 'cli':

            self.appConfig.console.print('')
            self.appConfig.console.print(f'[yellow]{message}.')

            response1 = click.prompt('Enter your secret',hide_input=True,default='n',show_default=False)
            response2 = click.prompt('Re-enter your secret',hide_input=True,default='n',show_default=False)

            if response1.lower() == 'n':
                return False
            if response1 != response2:
                return self.prompt_to_change_secret('Secrets do not match.')
            else:
                try:
                    self.update_aws_cow_account_secret(response1,True)
                    return True
                except Exception as e:
                    self.logger.error(f"Failed to update AWS secret: {str(e)}")
                    return False


        if self.appConfig.mode == 'module':
            self.appConfig.alerts['encryption_secret'] = 'New Encryption Secret Required'
            