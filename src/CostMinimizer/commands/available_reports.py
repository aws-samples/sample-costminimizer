# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..constants import __tooling_name__

from rich import print
from rich.layout import Layout
import tabulate as tabulate
from ..report_controller.report_controller import CowReportController

class AvailableReportsCommand:
    
    def __init__(self, appInstance, writer=None) -> None:
        self.appInstance = appInstance
        self.appConfig = appInstance.config_manager.appConfig
        self.layout = Layout()
        self.writer = writer
            
    def run(self):
        all_available_reports = {}
        available_reports = []

        providers = CowReportController(self.appConfig, self.writer).import_reports( force_all_providers_true=True)

        if self.appInstance.AppliConf.mode == 'cli':
            self.appConfig.console.rule( f"{__tooling_name__} Tooling Available Reports", style="white on blue")
            #print("")

            self.layout.split_row(
                Layout(name="left"),
                Layout(name="right"),
            )

        for provider in providers:
            reports = provider(self.appConfig).get_available_reports(return_available_report_objects=True)

            all_available_reports[provider] = reports

        tab = []
        tab.append( ('OPTIMIZER TOOL', 'NAME OF CHECK', 'COST OPTIMIZATION TITLE'))     
        for report_provider in all_available_reports:
            for report in all_available_reports[report_provider]:
                self.appConfig.console.print(f'[green]Man Page - [yellow]{report.service_name(self)}')
                self.appConfig.console.print(f'[green]Description: [blue]{report.common_name(self)}')
                self.appConfig.console.print(f'[green]Summary: [white]{report.long_description(self)}')
                print(f'\n')
                tab.append((report.service_name(self), report.name(self), report.description(self)))   

        self.appConfig.console.print(tabulate.tabulate(tab, headers="firstrow", tablefmt="pretty"))
        self.appConfig.console.print(f'\n # of checks : {len(tab)}\n')

        if self.appInstance.AppliConf.mode == 'module':
            return all_available_reports

    def get_report_providers(self) -> list:
        '''get all report providers in app'''
        return CowReportController(self.appConfig, self.writer).import_reports( force_all_providers_true=False)

    def get_all_available_reports(self) -> list:
        '''return list of all available reports'''
        all_reports = []
        for provider in self.get_report_providers():
            reports = provider(self.appConfig).get_available_reports(return_available_report_objects=True)
            all_reports.extend(reports)

        return all_reports
