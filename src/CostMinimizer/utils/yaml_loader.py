# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import yaml

def import_yaml_file(yaml_file, operation="r"):
    try:
        with open(yaml_file, operation) as stream:
            try:
                fh = yaml.safe_load(stream)
            except yaml.scanner.ScannerError as e:
                raise YamlFileSyntaxError(f'You have an error in your yaml file syntax {yaml_file}')
            except yaml.YAMLError as e:
                print(e)
                raise
        return fh
    except Exception as e:
        raise

def dump_configuration_to_file(dump_file, dict_data) -> bool:
    try:
        with open(dump_file, "w") as stream:
            yaml.dump(dict_data, stream, default_flow_style=False)
        return True
    except IOError:
        print(f"IOERROR : Unable to write into file: {dump_file}")
        
        return False

class YamlFileSyntaxError(Exception):
    pass


