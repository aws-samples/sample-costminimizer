# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

import logging
import hashlib
import logging


class CowMetrics:

    def __init__(self, appConfig, metrics_session_name:str = 'end') -> None:
        '''
        Collect program metrics, transform into JSON and write to a file
        '''
        self.appConfig     = appConfig
        self.metrics = {}

        self.logger = logging.getLogger(__name__)

        '''
        In the future we may want to send metrics at the start of the COW tool as well as the end.
        Curently we are only sending in metrics at the end or program completion.
        '''
        self.metrics_session_name = metrics_session_name
        self.duration             = None

        #unique ID for this installation - based on users admin account
        self.metrics['uid'] = self.create_unique_id(str(self.appConfig.config['aws_cow_account']))

    def create_unique_id(self, account) -> str:
        '''create a unique has string based on users admin account'''
        uid = hashlib.sha256(bytes(account, 'utf-8')).hexdigest()

        return uid
    
    def submit(self, metrics:dict) -> None: 
        '''method to collect metircs and update the dict'''
        self.metrics.update(metrics)

    def set_running_time(self, start, end) -> None:
        '''method to calculate the duration of the program run'''
        if self.metrics_session_name == 'end':
            self.duration = end - start

            metric = {'duration': float(self.duration.total_seconds())}
            self.submit(metric)

    def get_metrics(self) -> dict:
        '''method to return the metrics'''
        return self.metrics


