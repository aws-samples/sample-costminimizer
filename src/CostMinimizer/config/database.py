# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import logging
import os
import sqlite3
from .customer import Customer
from .report import Report
from typing import List
from ..config.database_updates import DatabaseUpdate
from pathlib import Path
import json
import csv

class UnableToUpdateSQLValue(Exception):
    pass

class InvalidBubblewandAccountNumber(Exception):
    pass

class UnableToDetermineBubblewandEmail(Exception):
    pass

class UnableToExecuteSqliteQuery(Exception):
    pass

class ToolingDatabase:

    def __init__(self, appConfig) -> None:
        '''class for interacting with the CostMinimizer database '''
        self.appConfig = appConfig
        self.logger = logging.getLogger(__name__)
        self.db = self.appConfig.internals['internals']['database']['database_file']
        if self.appConfig.installation_type in ('container_install'):
            self.database_directory = self.appConfig.local_home / self.appConfig.internals['internals']['database']['database_directory_for_container']
        else:
            self.database_directory = self.appConfig.local_home / self.appConfig.internals['internals']['database']['database_directory_for_local']

        self.database_file = self.database_directory / self.appConfig.internals['internals']['database']['database_file']

        if not self.database_directory.is_dir():
            os.mkdir(self.database_directory) 
        
        #make database cursor
        self.con = self.get_connection()
#        self.cursor = self.make_cursor()

        #creates database and tables if not exists
        self.create_tables()

        #table names
        self.customer_table_name = "cow_customerdefinition"
        self.payer_table_name = "cow_customerpayeraccounts"
        self.internals_parameters_table_name = "cow_internalsparameters"

    def connect_to_database(self) -> sqlite3.Connection:
        '''create a database if one does not exist'''
        try:
            return sqlite3.connect(self.database_file)
        except sqlite3.Error as e:
            self.logger.error(f"Error connecting to database: {e}")
            raise

    def get_connection(self) -> sqlite3.Connection:
        '''return sqllite connection'''
        return self.connect_to_database()

    # def make_cursor(self) -> sqlite3.Cursor:
    #     '''return sql connection cursor'''
    #     return self.con.cursor()

    def get_tables_list(self) -> list:
        '''return a list of all table definition function names (minus the _table)'''
        return [
            'cowconfiguration', 
            'customersdefinition', 
            'customerpayeraccounts', 
            'cowavailablereports', 
            'cowcustomercache', 
            'cowreporthistory',
            'cowinternalsparameters',
            'cowreportparameters', 
            'cowlogin',
            'cowawspricingdb',
            'cowawspricingec2',
            'cowgravitonconversion',
            'cowawspricinglambda']

    def get_tables_dict(self) -> list:
        '''return a list of all table definition function names (minus the _table)'''
        return {
            'cow_configuration': 'cow_configuration', 
            'cow_customerdefinition': 'cow_customerdefinition', 
            'cow_customerpayeraccounts': 'cow_customerpayeraccounts', 
            'cow_availablereports': 'cow_availablereports', 
            'cow_customercache': 'cow_customercache', 
            'cow_cowreporthistory': 'cow_cowreporthistory',
            'cow_internalsparameters': 'cow_internalsparameters',
            'cow_reportparameters': 'cow_reportparameters',
            'cow_login': 'cow_login',
            'cow_awspricingdb': 'cow_awspricingdb',
            'cow_awspricingec2': 'cow_awspricingec2',
            'cow_gravitonconversion': 'cow_gravitonconversion',
            'cow_awspricinglambda': 'cow_awspricinglambda'
            }


    def create_tables(self) -> None:
        '''loop through the table functions list and create all tables'''
        cursor = self.con.cursor()

        for table in self.get_tables_list():
            # get the SQL text that correspond to the name of the table
            sql = getattr(self, f"{table}_table")()
            parameters = ()
            cursor.execute(sql, parameters)

        cursor.close()

    def clear_table(self, table_name) -> None:
        '''clear all values from table'''

        # Clear only if the 
        sql = f"DELETE FROM {self.get_tables_dict()[table_name]}"
        try:
            cursor = self.con.cursor()
            parameters = ()
            cursor.execute(sql, parameters)
            self.con.commit()
            cursor.close()
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

    def process_table_schema_updates(self) -> None:
        '''process any schema updates necessary for tables of older version CostMinimizer Tooling'''
        du = DatabaseUpdate(self.appConfig).execute_updates()

    def run_sql_statement(self, sql) -> None:
        '''run provided sql statement'''

        try:
            cursor = self.con.cursor()
            cursor.execute(sql)
            self.con.commit()
            cursor.close()
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

    def select_records(self, sql, rows='all'):
        '''
        return result of select statement
        table_name = table name
        sql = full sql statement
        row = either 'one' for fetchone or all for fecthall (default)
        '''
        cursor = self.con.cursor()

        try:
            result = cursor.execute(sql)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        if rows == 'one':
            return result.fetchone()

        retVal = result.fetchall()

        cursor.close()

        return retVal

    def sanitize_customer_record(self, record, bubblewand_account = ""):
        def recordExistsAndNotNull(field):
            if field in record.keys() and len(record[field].strip()) > 0:
                record[field] = record[field].strip().replace(" ", "_")
                return True
            else:
                return False

        #customer record (bubblewand) specifics defined in cow_internals.yaml
        cow_internals_customer_discovery = self.appConfig.internals['internals']['cur_customer_discovery']

        if not recordExistsAndNotNull('cx_name'):
            raise Exception('Customer record requires a customer name.')

        if not recordExistsAndNotNull('email_address'):
            raise Exception('Customer record requires an email address.')

        if not recordExistsAndNotNull('aws_profile'):
            record['aws_profile'] = cow_internals_customer_discovery['aws_profile'].replace('{dummy_value}', record['cx_name'])

        if not recordExistsAndNotNull('secrets_aws_profile'):
            record['secrets_aws_profile'] = cow_internals_customer_discovery['secrets_aws_profile'].replace('{dummy_value}', record['cx_name'])

        if not recordExistsAndNotNull('athena_s3_buckt'):
            record['athena_s3_buckt'] = cow_internals_customer_discovery['aws_cow_s3_bucket'].replace('{dummy_value}', bubblewand_account)

        if not recordExistsAndNotNull('cur_db_name'):
            record['cur_db_name'] = cow_internals_customer_discovery['db_name']

        if not recordExistsAndNotNull('cur_db_table'):
            record['cur_db_table'] = cow_internals_customer_discovery['table']

        if not recordExistsAndNotNull('cur_region'):
            record['cur_region'] = cow_internals_customer_discovery['region']

        if not recordExistsAndNotNull('acc_regex'):
            record['acc_regex'] = ''

        if 'min_spend' not in record.keys():
            record['min_spend'] = 0

        if int(record['min_spend']) < 0:
            record['min_spend'] = 0

        if not recordExistsAndNotNull('account_email'):
            '''account email is discovered by k2 but it is not required'''
            pass

        return record

    def fetch_internals_parameters_table(self):
        
        # Fetch all rows and fetchone() returns None when no more rows are available
        rows = self.get_cow_internals_parameters()
        
        # Create a dictionary to store the data
        data_dict = {}
        
        for row in rows:
            parent, key, value = row[1], row[2], row[3]
            
            # Create nested dictionaries based on the parent hierarchy
            nested_dict = data_dict
            if parent:
                parent_keys = parent.split('.')
                for parent_key in parent_keys:
                    nested_dict = nested_dict.setdefault(parent_key, {})
            
            # Assign the value to the appropriate key
            if value.isdigit():
                nested_dict[key] = int(value)
            else:
                nested_dict[key] = value
        
        return data_dict

    def write_internals_parameters_table(self, data, parent_key=''):
        for key, value in data.items():
            if isinstance(value, dict):
                # Recursively handle nested dictionaries
                self.write_internals_parameters_table( value, f'{parent_key}.{key}' if parent_key else key)
            else:
                # Insert leaf-level key-value pairs into the SQLite3 table
                self.add_internals_parameters(parent_key, key, value, self.internals_parameters_table_name)

    def update_internals_parameters_table_from_yaml_file(self, data, parent_key='', list_fields_to_update = []):
        for key, value in data.items():
            if isinstance(value, dict):
                # Recursively handle nested dictionaries
                self.update_internals_parameters_table_from_yaml_file( value, f'{parent_key}.{key}' if parent_key else key, list_fields_to_update)
            else:
                if (key in list_fields_to_update):
                    # Insert leaf-level key-value pairs into the SQLite3 table
                    self.update_internals_parameters(parent_key, key, value, self.internals_parameters_table_name)

    def add_internals_parameters(self, parent_key, key, value, table_name):
        try:
            request = {'parent': parent_key, 'key': key, 'value': value}
            self.insert_record(request, table_name)
            return True
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

    def update_internals_parameters(self, parent_key, key, value, table_name):
        try:
            request = { 'value': value}
            self.update_record(request, table_name,  f"parent='{parent_key}' and key='{key}' ")
            return True
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e


    def update_customer(self, customer_id, customer_name, email_address, aws_profile,
            secrets_aws_profile, athena_s3_bucket, cur_db_name, cur_db_table,
            cur_region, customer_payer_account, min_spend = 0, acc_regex = '', account_email=""):
        record = {}

        customer_payer_account = str(customer_payer_account).strip()

        if len(customer_payer_account) == 11:
            customer_payer_account = customer_payer_account.zfill(12)

        if len(customer_payer_account) != 12:
            msg = f'Your bubblewand account number {customer_payer_account} must be 12 digits.'
            raise InvalidBubblewandAccountNumber(msg)

        try:
            record = {
                'cx_name': customer_name,
                'email_address': email_address,
                'aws_profile': aws_profile,
                'secrets_aws_profile': secrets_aws_profile,
                'athena_s3_buckt': athena_s3_bucket,
                'cur_db_name': cur_db_name,
                'cur_db_table': cur_db_table,
                'cur_region': cur_region,
                'min_spend': min_spend,
                'acc_regex': acc_regex,
                'account_email': account_email
            }

            self.sanitize_customer_record(record)

            self.update_record(record, self.customer_table_name, f"cx_id='{customer_id}'")

            payerRecord = {
                'payer_id': str(customer_payer_account),
                'account_id': str(customer_payer_account)
            }

            self.update_record(payerRecord, self.payer_table_name, f"cx_id_id='{customer_id}'")

            customerList = self.get_customer(record['cx_name'])

            return Customer(customerList[0])

        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

    def insert_record(self, request, table_name):
        '''function to abstract the insertion of records into our database'''
        keys = list(request.keys())
        values = list(request.values())

        placeholders = ', '.join(['?' for _ in keys])
        keys = ', '.join(keys)

        cursor = self.con.cursor()

        sql = f'INSERT INTO {self.get_tables_dict()[table_name]} ({keys}) VALUES ({placeholders})'
        parameters = tuple(str(i) for i in values)
        try:
            cursor.execute(sql, parameters)
            
            self.con.commit()
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        cursor.close()


    def update_record(self, request, table_name, where):
        '''function to abstract the update of records into our database'''
        keys = list(request.keys())
        values = list(request.values())
        sql_set = []

        for i in range(len(keys)):
            sql_set.append(f"{keys[i]} = ?")

        text_sql_set = ','.join(sql_set)
        self.logger.info(text_sql_set)

        cursor = self.con.cursor()

        sql = f'UPDATE {self.get_tables_dict()[table_name]} SET {text_sql_set} WHERE {where}'
        parameters = tuple(values)
        try:
            cursor.execute(sql, parameters)
            
            self.con.commit()
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        cursor.close()

    def cowconfiguration_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS "cow_configuration" (
            "config_id"	INTEGER,
            "aws_cow_account"	TEXT,
            "aws_cow_profile"	TEXT UNIQUE,
            "sm_secret_name"	TEXT,
            "output_folder"	TEXT,
            "installation_mode"	varchar(20) NOT NULL DEFAULT 'local_install',
            "container_mode_home"	varchar(20) NOT NULL DEFAULT '/root/.cow',
            "cur_db"	varchar(99) DEFAULT '',
            "cur_table"	varchar(99) DEFAULT '',
            "cur_region"	varchar(30) DEFAULT '',
            "aws_cow_s3_bucket"	varchar(100) DEFAULT '',
            "ses_send"	varchar(100) DEFAULT '',
            "ses_from"	varchar(100) DEFAULT '',
            "ses_region"	varchar(20) DEFAULT '',
            "ses_smtp"	varchar(50) DEFAULT '',
            "ses_login"	varchar(50),
            "ses_password"	varchar(50),
            "costexplorer_tags"	varchar(30) DEFAULT '',
            "costexplorer_tags_value_filter"	varchar(99) DEFAULT '',
            "graviton_tags"	varchar(30) DEFAULT '',
            "graviton_tags_value_filter"	varchar(99) DEFAULT '',
            "current_month"	varchar(5) DEFAULT 'FALSE',
            "day_month"	varchar(5) DEFAULT '',
            "last_month_only"	varchar(20) DEFAULT 'FALSE',
            "aws_access_key_id"	varchar(50),
            "aws_secret_access_key"	varchar(50),
            "cur_s3_bucket"	varchar(255) DEFAULT 's3://???/MyStandardExport',
            PRIMARY KEY("config_id" AUTOINCREMENT)
        )'''

        return sql

    def customersdefinition_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS "cow_customerdefinition" (
            "cx_id"	integer NOT NULL,
            "cx_name"	varchar(20) NOT NULL UNIQUE,
            "email_address"	varchar(256) NOT NULL DEFAULT 'email@email.com',
            "create_time"	datetime NOT NULL,
            "last_used_time"	datetime,
            "aws_profile"	varchar(256) NOT NULL,
            "secrets_aws_profile"	varchar(256) NOT NULL,
            "athena_s3_buckt"	varchar(256) NOT NULL,
            "cur_db_name"	varchar(256) NOT NULL,
            "cur_db_table"	varchar(256) NOT NULL,
            "cur_region"	varchar(256) NOT NULL,
            "min_spend"	integer NOT NULL,
            "acc_regex"	varchar(100) NOT NULL,
            "account_email" varchar(256),
            PRIMARY KEY("cx_id" AUTOINCREMENT)
        )'''

        return sql

    def cowreporthistory_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS
        "cow_cowreporthistory"
        ("hist_id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
        "report_id" varchar(64) NOT NULL,
        "report_name" varchar(100) NOT NULL,
        "report_provider" varchar(10) NOT NULL,
        "report_exec_id" varchar(100) NOT NULL,
        "parent_report" varchar(100),
        "start_time" datetime NOT NULL, 
        "status" varchar(10) NOT NULL, 
        "comment" varchar(1024), 
        "using_tags" varchar(10) NOT NULL,
        "cx_id_id" integer NOT NULL REFERENCES
        "cow_customerdefinition" ("cx_id") DEFERRABLE INITIALLY DEFERRED)'''

        return sql

    def customerpayeraccounts_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS
        "cow_customerpayeraccounts" (
        "payer_id"	TEXT NOT NULL,
	    "account_id"	TEXT NOT NULL,
        "cx_id_id"	integer NOT NULL,
        PRIMARY KEY("payer_id"),
        FOREIGN KEY("cx_id_id") REFERENCES "cow_customerdefinition"("cx_id") DEFERRABLE INITIALLY DEFERRED)'''

        return sql

    def cowavailablereports_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS "cow_availablereports" (
            "report_id"	INTEGER,
            "report_name"	TEXT UNIQUE,
            "report_description"	TEXT,
            "report_provider"	TEXT,
            "service_name"	TEXT,
            "display" TEXT,
            "common_name" TEXT,
            "long_description" TEXT,
            "domain_name" TEXT,
            "html_link" TEXT,
            "dante_link" TEXT,
            "configurable" TEXT,
            "report_parameters" TEXT,
            PRIMARY KEY("report_id" AUTOINCREMENT)
        );'''

        return sql

    def cowcustomercache_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS "cow_customercache" (
            "cache_id"	INTEGER NOT NULL,
            "partition_type"	TEXT NOT NULL,
            "account_discovery_expiration"	INTEGER NOT NULL DEFAULT 1,
            "report_expiration"	INTEGER NOT NULL DEFAULT 1,
            "cur_column_expiration"	INTEGER NOT NULL DEFAULT 1,
            "cx_id_id"	INTEGER NOT NULL,
            PRIMARY KEY("cache_id" AUTOINCREMENT)
        )'''

        return sql

    def cowreportparameters_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS "cow_reportparameters" (
            
            "report_name"	TEXT NOT NULL UNIQUE,
            "report_parameters"	TEXT NOT NULL,
            PRIMARY KEY("report_name" )
        )'''

        return sql

    def cowinternalsparameters_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS "cow_internalsparameters" (
            "param_id" INTEGER,
            "parent" TEXT,
            "key"	TEXT,
            "value"	TEXT,
            PRIMARY KEY("param_id" AUTOINCREMENT)
        )'''
        return sql

    def cowlogin_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS "cow_login" (
            "login_id"	INTEGER,
            "login_type"	TEXT DEFAULT 'secretsmanager',
            "login_timestamp"	TEXT,
            "login_cache_expiration" TEXT,
            "login_hash" TEXT,
            PRIMARY KEY("login_id" AUTOINCREMENT)
        );'''
        return sql

    # create cowawspricingdb table that read awsprincing.csv in the folder ./
    def cowawspricingdb_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS "cow_awspricingdb" (
            "awspricing_id"	INTEGER,
            "family"	TEXT,
            "instancetype"	TEXT,
            "databaseengine"	TEXT,
            "deploymentoption"	TEXT,
            "location"	TEXT,
            "odpriceperunit"	FLOAT,
            "ripriceperunit"	FLOAT
        );'''
        return sql


    # create cowawspricingec2 table that read awsprincing.csv in the folder ./
    def cowawspricingec2_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS "cow_awspricingec2" (
            "awspricing_id"	INTEGER,
            "ConcatField"	TEXT,
            "Column1"	TEXT,
            "vcpu"	INTEGER,
            "Family"	TEXT,
            "odpriceperunit"	FLOAT,
            "ripriceperunit"	FLOAT,
            "svpriceperunit"	FLOAT
        );'''
        return sql


    # create cowgravitonconversion table that read gravitonconversion.csv with columns Family,Generation,Latest Intel,Latest AMD,Graviton2,Graviton3,Graviton4,Previous Intel,Default Graviton Equivalent,Latest Elasticsearch Intel
    def cowgravitonconversion_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS cow_gravitonconversion (
            Family TEXT,
            Generation TEXT,
            Latest_Intel TEXT,
            Latest_AMD TEXT,
            Graviton2 TEXT,
            Graviton3 TEXT,
            Graviton4 TEXT,
            Previous_Intel TEXT,
            Default_Graviton_Equivalent TEXT,
            Latest_Elasticsearch_Intel TEXT
        );'''
        return sql

    # create cowawspricinglambda table that read lambdapricings.csv with columns location,usagetype,odpriceperunit,svpriceperunit
    def cowawspricinglambda_table(self):
        sql = '''CREATE TABLE IF NOT EXISTS cow_awspricinglambda (
            location TEXT,
            usagetype TEXT,
            odpriceperunit FLOAT,
            svpriceperunit FLOAT
        );'''
        return sql


    # More robust version with transaction and error handling
    def import_sql_dump_with_validation(self, database_path, sql_file_path):
        """
        Import a SQL dump file with additional error handling and validation
        
        Args:
            database_path: Path to the SQLite database
            sql_file_path: Path to the SQL dump file
        """
        # Convert paths to Path objects for cross-platform compatibility
        db_path = Path(database_path)
        sql_path = Path(sql_file_path)
        
        # Validate files exist
        if not sql_path.exists():
            raise FileNotFoundError(f"SQL file not found: {sql_path}")
        
        try:
            # Create connection with extended timeout
            cursor = self.con.cursor()
            
            # Optimize for bulk import
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA cache_size = -2000")  # Use 2GB memory for cache
            cursor.execute("PRAGMA temp_store = MEMORY")
            
            # Read and execute SQL file in chunks whith encode utf8
            with open(sql_path, 'r', encoding='utf8') as sql_file:

                sql_script = sql_file.read()
                
                # Split script into individual statements
                statements = sql_script.split(';')
                line_num = 0
                
                for statement in statements:
                    statement = statement.strip()
                    if statement:  # Skip empty statements
                        try:
                            cursor.execute(statement)
                            line_num = line_num + 1
                            if line_num % 1000 == 0:
                                self.appConfig.console.print(".", end="")
                        except sqlite3.Error as e:
                            print(f"Error executing statement: {statement[:100]}...")
                            print(f"Error message: {e}")
                            raise
            
            # Commit transaction
            # cursor.commit()
            
            # Verify import (optional)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            self.logger.info(f"Tables in database after import: {[table[0] for table in tables]}")
            
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            raise
        except Exception as e:
            print(f"Error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    # function that read all record from ./cow_awsprincing.sql file and insert the records into cow_awspricingdb table
    def insert_awspricingdb(self):
        # check if cow_awspricing containts more than 1 line
        cursor = self.con.cursor()
        sql = 'select count(*) from cow_awspricingdb'
        try:
            result = cursor.execute(sql)
            count = result.fetchone()[0]
            if count <= 0:
                self.appConfig.console.print("[yellow]\nImporting pricing informations for instances from cow_awsprincing.sql, please wait...")

                # import cow_awspricingdb.sql file
                file_path = os.path.join("src", "CostMinimizer", "config", "cow_awspricingdb.sql")
                self.import_sql_dump_with_validation( 'cow_awspricingdb', file_path)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e
        cursor.close()

    # function that read all record from ./cow_awspricingec2.sql file and insert the records into cow_awspricingec2 table
    def insert_awspricingec2(self):
        # check if cow_awspricingec2 containts more than 1 line
        cursor = self.con.cursor()
        sql = 'select count(*) from cow_awspricingec2'
        try:
            result = cursor.execute(sql)
            count = result.fetchone()[0]
            if count <= 0:
                self.appConfig.console.print("[yellow]\nImporting pricing informations for instances from cow_awspricingec2.sql, please wait...")

                # import cow_awspricingec2.sql file
                file_path = os.path.join("src", "CostMinimizer", "config", "cow_awspricingec2.sql")
                self.import_sql_dump_with_validation( 'cow_awspricingec2', file_path)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e
        cursor.close()

    # function that read all record from ./cow_gravitonconversion.sql file and insert the records into cow_gravitonconversion table
    def insert_gravitonconversion(self):
        # check if cow_gravitonconversion containts more than 1 line
        cursor = self.con.cursor()
        sql = 'select count(*) from cow_gravitonconversion'
        try:
            result = cursor.execute(sql)
            count = result.fetchone()[0]
            if count <= 0:
                self.appConfig.console.print("[yellow]Importing graviton conversion informations for instances from cow_gravitonconversion.sql, please wait...")

                # import gravitonconversion.csv file
                file_path = os.path.join("src", "CostMinimizer", "config", "cow_gravitonconversion.sql")
                self.import_sql_dump_with_validation( 'cow_gravitonconversion', file_path)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e
        cursor.close()

    # function that read all record from ./cow_awspricinglambda.sql file and insert the records into cow_awspricinglambda table
    def insert_awspricinglambda(self):
        # check if cow_gravitonconversion containts more than 1 line
        cursor = self.con.cursor()
        sql = 'select count(*) from cow_awspricinglambda'
        try:
            result = cursor.execute(sql)
            count = result.fetchone()[0]
            if count <= 0:
                self.appConfig.console.print("[yellow]\nImporting pricing informations for lambda from cow_awspricinglambda.sql, please wait...")

                # import gravitonconversion.csv file
                file_path = os.path.join("src", "CostMinimizer", "config", "cow_awspricinglambda.sql")
                self.import_sql_dump_with_validation( 'cow_gravitonconversion', file_path)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e
        cursor.close()


    # function that as a type of instance in parameters and results the unit price read from cow_awsprincing table
    def get_ec2instance_price_from_db(self, instance_family, region, operating_system, tenancy, pre_installed_software):
        cursor = self.con.cursor()

        if 'Windows' == operating_system or \
            'RHEL' == operating_system or \
            'Ubuntu Pro' == operating_system or \
            'SUSE' == operating_system or \
            'Ubuntu Pro' == operating_system or \
            'Linux' == operating_system or \
            'Linux with HA' == operating_system or \
            'Red Hat Enterprise Linux with HA' == operating_system:
            l_operating_system = operating_system+'NA'
        else:
            l_operating_system = operating_system

        # check if region is a tuple type
        if isinstance(region, tuple):
            conditions = [f"ConcatField = '{instance_family}{value}{l_operating_system}'" for value in region]
            sql_condition = " OR ".join(conditions)
                
        else:
            sql_condition = f"ConcatField = '{instance_family}{region}{l_operating_system}'"

        sql = f"select ConcatField,Column1,vcpu,Family,odpriceperunit,ripriceperunit,svpriceperunit from cow_awspricingec2 where {sql_condition}"
        try:
            result = cursor.execute(sql)
            l_fetchone = result.fetchone()
            if (l_fetchone is not None):
                unit_price = float(l_fetchone[4])
            else:
                unit_price = float(0)
            cursor.close()
            return unit_price
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

    # function that as a type of instance in parameters and results the unit price read from cow_awsprincing table
    def get_dbinstance_price_from_db(self, instance_family, region, database_engine, deployment_option, pre_installed_software):
        cursor = self.con.cursor()

        sql_condition = f" instancetype = '{instance_family}' AND "

        # check if region is a tuple type
        if isinstance(region, tuple):
            conditions = [f" location = '{value}'" for value in region]
            sql_condition = sql_condition + "(" + " OR ".join(conditions) + ")"
                
        else:
            sql_condition = sql_condition + f" location = '{region}'"

        sql_condition = sql_condition  + f" AND databaseengine = '{database_engine}'"

        sql_condition = sql_condition  + f" AND deploymentoption = '{deployment_option}'"

        sql = f"select family,instancetype,databaseengine,deploymentoption,location,odpriceperunit,ripriceperunit from cow_awspricingdb where {sql_condition}"
        try:
            result = cursor.execute(sql)
            l_fetchone = result.fetchone()
            if (l_fetchone is not None):
                unit_price = float(l_fetchone[5])
            else:
                unit_price = float(0)
            cursor.close()
            return unit_price
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

    # function that as a type of instance in parameters and results the unit price read from cow_awsprincing table
    def get_lambda_price_from_db(self, region, usage_type):
        cursor = self.con.cursor()

        sql_condition = f" usagetype = '{usage_type}' AND "

        # check if region is a tuple type
        if isinstance(region, tuple):
            conditions = [f" location = '{value}'" for value in region]
            sql_condition = sql_condition + "(" + " OR ".join(conditions) + ")"
                
        else:
            sql_condition = sql_condition + f" location = '{region}'"

        sql = f"select location,usagetype,odpriceperunit,svpriceperunit from cow_awspricinglambda where {sql_condition}"
        try:
            result = cursor.execute(sql)
            l_fetchone = result.fetchone()
            if (l_fetchone is not None):
                unit_price = float(l_fetchone[2])
            else:
                unit_price = float(0)
            cursor.close()
            return unit_price
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

    # get graviton equivalent from an instance type in parameter and using cow_gravitonconversion table
    def get_graviton_equivalent_from_db(self, instance_type):
        cursor = self.con.cursor()
        sql = "select Graviton2, Graviton3, Graviton4, Default_Graviton_Equivalent from cow_gravitonconversion where family = '{}' ".format(instance_type)
        try:
            result = cursor.execute(sql)
            # get result[2] if value is not '' otherwise result[1] if value is not '' or result[0]
            graviton_equivalence = result.fetchone()
            if graviton_equivalence[3] != '':
                graviton_equivalence = graviton_equivalence[3]
            elif graviton_equivalence[2] != '':
                graviton_equivalence = graviton_equivalence[2]
            elif graviton_equivalence[1] != '':
                graviton_equivalence = graviton_equivalence[1]
            else:
                graviton_equivalence = graviton_equivalence[0]
            cursor.close()
            return graviton_equivalence
        except Exception as e:
            self.logger.error(f"Database.error: {str(e)}")
            raise e


    def get_cow_configuration(self) -> list:
        '''return dictionary of cow configuration parameters'''

        try:
            sql = 'select * from cow_configuration'
            cursor = self.con.cursor()            
            result = cursor.execute(sql)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        retVal = result.fetchall()

        cursor.close()
        return retVal

    def get_cow_internals_parameters(self) -> list:
        '''return dictionary of cow configuration parameters'''

        cursor = self.con.cursor()

        sql = 'select * from cow_internalsparameters'
        try:
            result = cursor.execute(sql)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        retVal = result.fetchall()

        cursor.close()
        return retVal

    def get_cow_internals_parameters(self) -> list:
        '''return dictionary of cow configuration parameters'''

        cursor = self.con.cursor()

        sql = 'select * from cow_internalsparameters'
        try:
            result = cursor.execute(sql)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        return result.fetchall()


    def get_customer_id(self, customer_name) -> list:
        '''return a list of the customer's ID'''
        sql = f"select cx_id from {self.get_tables_dict()[self.customer_table_name]} where cx_name = ?"
        parameters = customer_name,
        # cursor db is not local
        try:
             cursor = self.con.cursor() # cursor is now local
             result = cursor.execute(sql, parameters)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        retVal = result.fetchone()
        cursor.close()
        return retVal

    def get_all_customers(self) -> List[Customer]:
        '''return all customers'''
        cursor = self.con.cursor()

        sql = f"select * from {self.get_tables_dict()[self.customer_table_name]}"
        try:
            result = cursor.execute(sql)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        customers = []
        for row in result.fetchall():
            customer_name = row[1]
            payer_account = self.get_customer_payers(customer_name)

            if isinstance(payer_account, tuple):
                payer_account = payer_account[0] #first column is payer_id

            customers.append(Customer(row, payer_account))

        cursor.close()
        return customers

    def get_customer(self, customer_name) -> List[Customer]:
        '''return customer by name'''
        cursor = self.con.cursor()

        sql = f"select * from {self.get_tables_dict()[self.customer_table_name]}  WHERE cx_name = ?"
        parameters = customer_name,
        try:
            result = cursor.execute(sql, parameters)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        retVal = [Customer(row) for row in result.fetchall()]
        cursor.close()
        return retVal


    def get_customer_payers(self, customer_name) -> list:
        cx_id = self.get_customer_id(customer_name)

        if type(cx_id) == tuple:
            cx_id = cx_id[0]

            sql = f"SELECT * FROM {self.get_tables_dict()[self.customer_table_name]} WHERE cx_id_id = ?"
            parameters = cx_id
            try:
                cursor = self.con.cursor()
                result = cursor.execute(sql, parameters)
                retVal = result.fetchone()
                cursor.close()
            except Exception as e:
                self.logger.error(f"Database error: {str(e)}")
                raise e
            return retVal
        else:
            return []


    def get_available_reports(self) -> List[Report]:
        '''return available reports'''

        sql = "select * from cow_availablereports order by service_name, report_name"
        cursor = self.con.cursor()

        try:
            result = cursor.execute(sql)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        reports = []
        for row in result.fetchall():
            reports.append(Report(row))

        cursor.close()
        return reports
    
    def get_configurable_reports(self)->List:
        '''return available reports'''
        
        cursor = self.con.cursor()

        sql = "select common_name, configurable, report_parameters from cow_availablereports order by common_name"
        try:
            result = cursor.execute(sql)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        reports = []
        for row in result.fetchall():
            reports.append(row)

        return reports
    
    def get_report_parameters(self, report_name)->List:
        '''return available reports'''
        cursor = self.con.cursor()

        sql = "select report_parameters from cow_reportparameters where report_name = ?"
        parameters = report_name,
        try:
            result = cursor.execute(sql, parameters)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        reports = []
        for row in result.fetchall():
            reports.append(row)

        return reports
    
    def update_report_parameters(self, report_name, report_parameters):
        '''upsert cow_reportparameters table with new or updated cow report parameters'''

        report_dict={}
        report_dict[report_name]=report_parameters
        report_dict = json.dumps(report_dict)
        
        cursor = self.con.cursor()
        parameters = report_name, report_dict, report_dict, report_name

        sql = "insert into cow_reportparameters (report_name, report_parameters) values (?, ?) on conflict(report_name) do update set report_parameters = ? where report_name = ?"
        try:
            cursor.execute(sql, parameters)
            self.con.commit()
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

    def delete_report(self, customer, report_time):
        # delete report history record for a given report_id
        table_name = 'cow_cowreporthistory'
        cursor = self.con.cursor()

        cx_id = self.get_customer_id(customer)[0]

        sql = f"DELETE FROM \"main\".\"{self.get_tables_dict()[self.customer_table_name]}\" WHERE \"start_time\" = ? AND \"cx_id_id\" = ?"
        parameters = report_time, cx_id
        try:
            cursor.execute(sql, parameters)
            self.con.commit()
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        self.logger.info(f"Report '{customer}-{report_time}' deleted.")
        cursor.close()
        return None


    def update_table_value(self, table_name, column_name, id, new_value, sql_provided=None) -> None:
        '''update value for table where key lookup is cx_id'''

        if sql_provided is None:
            sql = f"UPDATE \"{self.get_tables_dict()[table_name]}\" SET \"{column_name}\" = ? WHERE \"cx_id\" = ?"
        else:
            sql = sql_provided
        cursor = self.con.cursor()

        try:
            parameters = new_value, id
            result = cursor.execute(sql, parameters)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        if result.rowcount != 1:
            msg = f"Unable to update table:{table_name}, column:{column_name}, cx_id:{id}, value:{new_value}"
            self.logger.exception(msg)
            raise UnableToUpdateSQLValue(msg)

        self.con.commit()

        cursor.close()

        return None

    def get_configuration(self):
        '''return cow configuration'''
        cursor = self.con.cursor()

        sql = 'SELECT * FROM cow_configuration'
        try:
            result = cursor.execute(sql)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        retVal = result.fetchall()
        cursor.close()
        return retVal

    def table_colum_check(self, table_name, column_name) -> bool:
        '''return true if column exists false if not exists'''
        sql = "select %s from %s"
        parameters = (column_name, self.get_tables_dict()[table_name])

        try:
            cursor = self.con.cursor()
            cursor.execute(sql, parameters)
        except:
            return False
        finally:
            cursor.close()

        return True

    def get_table_schema(self, table_name) -> list:
        '''return table schema '''

        sql = "PRAGMA table_info(?)"
        result = []

        try:
            cursor = self.con.cursor()            
            result = cursor.execute(sql, (self.get_tables_dict()[table_name],)).fetchall()
        except:
            msg = f'Unable to retreive schema for table: {table_name}'
            UnableToExecuteSqliteQuery(msg)
        finally:
            cursor.close()

        return result

    def get_secrets_manager_name(self) -> str:
        '''return secrets manager name'''

        column_name = 'sm_secret_name'

        cursor = self.con.cursor()

        sql = "select {} from {}".format(column_name, self.get_tables_dict()['cow_configuration'])
        try:
            parameters = ()
            result = cursor.execute(sql, parameters)
        except Exception as e:
            self.logger.error(f"Database error: {str(e)}")
            raise e

        retVal = result.fetchone()[0]

        cursor.close()

        return retVal
