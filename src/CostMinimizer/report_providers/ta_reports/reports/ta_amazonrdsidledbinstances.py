# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

__author__ = "Samuel Lepetre"
__license__ = "Apache-2.0"

from ..ta_base import TaBase
import pandas as pd
from rich.progress import track

class TaAmazonrdsidledbinstances(TaBase):

	def name(self): #required - see abstract class
		return 'ta_amazonrdsidledbinstances'

	def service_name(self):
		return 'Trusted Advisor'
	
	def domain_name(self):
		return 'COMPUTE'

	def common_name(self) -> str:
		return 'Amazon RDS Idle DB Instances'


	def description(self): #required - see abstract class
		return "Identifies Trusted Advisor Amazon RDS Idle DB Instances."
	
	def long_description(self) -> str:
		return f'''Identifies Trusted Advisor Amazon RDS Idle DB Instances.
		Checks the configuration of your Amazon Relational Database Service (Amazon RDS) for any DB instances that appear to be idle. 
		If a DB instance has not had a connection for a prolonged period of time, you can delete the instance to reduce costs. '''

	def author(self) -> list: 
		return ['slepetre']

	def supports_user_tags(self) -> bool:
		return True

	def is_report_configurable(self) -> bool:
		return True

	def _set_recommendation(self):
		self.recommendation = f'''Returned {self.count_rows()} rows summarizing Amazon RDS Idle DB Instances. '''

	def report_type(self):
		return 'processed'
	
	def report_provider(self):
		return 'ta'
	
	def savings_plan_enabled(self) -> bool:
		if 'savings_plan_savings_plan_a_r_n' in self.columns:
			return True
		
		return False
	
	def reservations_enabled(self) -> bool:
		if 'reservation_reservation_a_r_n' in self.columns:
			return True

		return False

	def disable_report(self) -> bool:
		return False

	def display_in_menu(self) -> bool:
		return True

	def override_column_validation(self) -> bool:
		#see description in parent class
		return True

	def get_estimated_savings(self, sum=True) -> float:
		self._set_recommendation()
		
		return self.set_estimate_savings( sum)

	def set_estimate_savings(self, sum=False) -> float:
		
		df = self.get_report_dataframe()

		if sum and (df is not None) and (not df.empty) and (self.ESTIMATED_SAVINGS_CAPTION in df.columns):
			return float(round(df[self.ESTIMATED_SAVINGS_CAPTION].astype(float).sum(), 2))
		else:
			return 0.0

	def calculate_savings(self):
		df = self.get_report_dataframe()
		try:
			return df[self.ESTIMATED_SAVINGS_CAPTION].sum()
		except:
			return 0

	def count_rows(self) -> int:
		try:
			return self.report_result[0]['Data'].shape[0]
		except Exception as e:
			self.appConfig.logger.warning(f"Error in counting rows: {str(e)}")
			return 0

	def enable_comparison(self) -> bool:
		return False

	def addTaReport(self, client, Name, CheckId, Display = True):
		type = 'chart'  # default type

		response = client.describe_trusted_advisor_check_result(checkId=CheckId)
        
		data_list = []
        
		if response['result']['status'] == 'not_available':
			self.appConfig.logger.info(f"No resources found for checkid {CheckId}.")
		else:
			for resource in response['result']['flaggedResources']:
				data_dict = {
                    self.get_required_columns()[0]: resource['region'],
                    self.get_required_columns()[1]: resource['metadata'][1],
                    self.get_required_columns()[2]: resource['metadata'][2],
                    self.get_required_columns()[3]: resource['metadata'][3],
                    self.get_required_columns()[4]: resource['metadata'][-1],
                    self.get_required_columns()[5]: float(resource['metadata'][4].replace('$', '').replace(',', ''))
                }
				data_list.append(data_dict)
        
		df = pd.DataFrame(data_list)
		self.report_result.append({'Name': Name, 'Data': df, 'Type': type})

	def get_required_columns(self) -> list:
		return [
                "Region",
                "InstanceID",
                "Name",
                "Type",
                "Days_idle",
                self.ESTIMATED_SAVINGS_CAPTION
            ]

    # return range definition of the categories in the excel graph
	def get_range_categories(self):
		# Col1, Lig1 to Col2, Lig2
		return 1, 0, 1, 0

    # return list of columns values in the excel graph so that format is $, which is the Column # in excel sheet from [0..N]
	def get_range_values(self):
        # Col1, Lig1 to Col2, Lig2
		return 10, 1, 10, -1