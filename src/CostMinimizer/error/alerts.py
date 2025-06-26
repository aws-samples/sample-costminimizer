# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

from ..patterns.singleton import Singleton


@dataclass
class AlertState(Singleton):
    """Data class for managing application alerts"""
    alerts: Dict[str, Any] = field(default_factory=lambda: {
        'aws_cow_profile': None,
        'midway': None,
        'customer_not_found': None,
        'report_failure': None,
        'missing_secret': None,
        'incorrect_secret': None,
        'secret_not_validated': None,
        'secret_confirmation_error': None,
        'secret_updated_successfully': None,
        'cache_file_error': None,
        'comparison': None,
        'async_status': None,
        'async_success': [],
        'async_unfinished': None,
        'async_fail': [],
        'async_error': [],
        'async_message': [],
        'calculate_fail': [],
        'calculate_success': []
    })