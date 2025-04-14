# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "samuel LEPETRE"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from ..reports_comparison.reports_comparison import CowReportComparison
from ..report_controller.report_controller import CowReportController

class ComparisonReportsCommand:
    
    def __init__(self, appConfig) -> None:
        self.appConfig = appConfig

    def get_report_providers(self) -> list:
        '''get all report providers in app'''
        return CowReportController(self.appConfig, self.writer).import_reports( force_all_providers_true = True)

    def get_all_available_reports(self) -> list:
        '''return list of all available reports'''
        all_reports = []
        for provider in self.get_report_providers():
            reports = provider(self.appConfig, {}).get_available_reports(return_available_report_objects=True)
            all_reports.extend(reports)
        
        return all_reports

    def run(self):
        reports = self.get_all_available_reports()
        comparisons = CowReportComparison(self.appConfig, reports).run