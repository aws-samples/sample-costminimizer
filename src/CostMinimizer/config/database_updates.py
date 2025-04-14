# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

class DatabaseUpdate:
    '''
    Processs updates to the database 

    The purpose of the methods in this class is to process updates 
    to the database so we can prevent the user from having to upgrade 
    database schema
    '''

    def __init__(self, appConfig) -> None:
        self.appConfig = appConfig

    def execute_updates(self):
        return

    def check_for_column(self, table_name:str, find_column_name:str) -> bool:
        '''Return True if column exists'''

        schema = self.appConfig.database.get_table_schema(table_name)

        found_column = False

        for column in schema:
            schema_column_name = column[1]
            if schema_column_name == find_column_name:
                found_column = True

        return found_column

    def add_column_if_not_exist(self, table_name:str, column_name:str, text=False, char_length=256):
        '''add domain name into the cow_customerdefinition table'''

        if not self.check_for_column(table_name, column_name):
            
            if text:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT"
            else:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} VARCHAR({char_length}) NOT NULL DEFAULT ''"

            self.appConfig.database.run_sql_statement(sql)



