# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ....report_providers.ce_reports.ce_base import CeBase


class CeTotalchange(CeBase):

	'''report file to query for all ebs spend from CUR'''
	def __init__(self, app) -> None:
		super().__init__(app)
		self.lookback_period = 6 # set to -1 for default, 0 = current month or number of months
		self.report_dependency_list=[]

	def get_report_parameters(self) -> dict:

		#{report_name:[{'parameter_name':'value','current_value':'value','allowed_values':['val','val','val']} ]}
		return {'CostExplorer Total View':[{'parameter_name':'lookback_period','current_value':6,'allowed_values':['1','2','3','4','5','6','7','8','9','10','11','12']} ]}

	def set_report_parameters(self,params)	-> None:
		''' Set the parameters to values pulled from DB'''

		param_dict = self.get_parameter_list(params)
		self.lookback_period = int(param_dict['Account Spend View'][0]['current_value'])
		
	def supports_user_tags(self) -> bool:
		return True

	def is_report_configurable(self) -> bool:
		return True
	
	def author(self) -> list: 
		return ['slepetre']
	
	def name(self): #required - see abstract class
		return 'ce_totalchange'

	def long_name(self):
		return CeBase.long_name()

	def common_name(self) -> str:
		return 'CHANGE TOTAL view'
	
	def service_name(self):
		return 'Cost Explorer'
	
	def domain_name(self):
		return 'Overall'

	def description(self): #required - see abstract class
		return '''Montly CostExplorer Total Spend View.'''
	
	def long_description(self) -> str:
		return f'''CostExplorer Total Spend View:
		This report focuses on cost changes across AWS total over time.
		Unlike the regular Total view, this report highlights:
		- Month-over-month total cost variations
		- Percentage changes in spend
		- Identification of total with significant cost increases or decreases
		Use this view to quickly spot trends and anomalies in total spending patterns'''
	
	def _set_recommendation(self):
		self.recommendation = f'''Returned {self.count_rows()} rows summarizing customer monthly spend. No estimated savings recommendation is provided by this report.  Query provides account information useful for cost optimization.'''
	
	def get_report_html_link(self) -> str:
		'''documentation link'''
		return '#'

	def report_type(self):
		return 'processed'
	
	def report_provider(self):
		return 'ce'
	
	def savings_plan_enabled(self) -> bool:
		if 'savings_plan_savings_plan_a_r_n' in self.columns:
			return True
		
		return False
	
	def reservations_enabled(self) -> bool:
		if 'reservation_reservation_a_r_n' in self.columns:
			return True

		return False

	def get_required_columns(self) -> list:
		return ['bill_payer_account_id', 'line_item_usage_account_id', 'month_line_item_usage_start_date',
	  'sum_line_item_unblended_cost', 'amortized_cost', 'ri_sp_trueup', 'ri_sp_upfront_fees']


	def get_expected_column_headers(self) -> list:
		return ['bill_payer_account_id', 'line_item_usage_account_id', 'month_line_item_usage_start_date',
	  'sum_line_item_unblended_cost', 'amortized_cost', 'ri_sp_trueup', 'ri_sp_upfront_fees']

	def disable_report(self) -> bool:
		return False

	def display_in_menu(self) -> bool:
		return True

	def override_column_validation(self) -> bool:
		#see description in parent class
		return True

	def get_estimated_savings(self, sum=False) -> float:
		self._set_recommendation()
		
		return self.set_estimate_savings()

	def set_estimate_savings(self, sum=False) -> float:

		return 0.0

	def count_rows(self) -> int:
		'''Return the number of rows found in the dataframe'''
		try:
			return self.calculate_savings().shape[0]
		except:
			return 0
	
	def calculate_savings(self):
		df = self.get_report_dataframe()
		
		#nothing to calculate for this check we just sum up the column 'ebs_gp3_potential_savings'
		return df

	def enable_comparison(self) -> bool:
		return False
			
	def get_comparison_definition(self) -> dict:
		'''Return dictionary of values required for comparison engine to function'''
		return { 
            'CSV_ID' : self.name(),
            'CSV_TITLE' : self.common_name(),
            'CSV_COLUMNS' : self.get_expected_column_headers(),
            'CSV_COLUMN_SAVINGS' : None,
            'CSV_GROUP_BY' : [],
            'CSV_COLUMNS_XLS' : [],
            'CSV_FILENAME' : self.name() + '.csv'
        }         	

	def sql(self, replace=True, query_type='sql_s_r'): #required - see abstract class
		return { "Name":"TotalChange", "GroupBy": [], "Style": 'Change', "IncSupport": True }

    # return chart type 'chart' or 'pivot' or '' of the excel graph
	def set_chart_type_of_excel(self):
		self.chart_type_of_excel = 'chart'
		return self.chart_type_of_excel