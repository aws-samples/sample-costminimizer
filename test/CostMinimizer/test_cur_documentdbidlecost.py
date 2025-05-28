import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import datetime
from datetime import timezone
import sys
import os

# Add the src directory to the path so we can import the module
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from CostMinimizer.report_providers.cur_reports.reports.cur_documentdbidlecost import CurDocumentdbidlecost, Cloudwatch

class TestCurDocumentdbidlecost(unittest.TestCase):
    
    def setUp(self):
        self.cur_documentdbidlecost = CurDocumentdbidlecost()
        self.cur_documentdbidlecost.logger = MagicMock()
        self.cur_documentdbidlecost.appConfig = MagicMock()
        self.cur_documentdbidlecost.appConfig.selected_regions = ['us-east-1']
        self.cur_documentdbidlecost.appConfig.selected_accounts = ['123456789012']
        self.cur_documentdbidlecost.report_result = []
    
    def test_get_cloudwatch_dicts(self):
        """Test the get_cloudwatch_dicts method"""
        db_list = [
            {'dBClusterIdentifier': 'test-cluster-1'},
            {'dBClusterIdentifier': 'test-cluster-2'}
        ]
        
        result = self.cur_documentdbidlecost.get_cloudwatch_dicts(db_list)
        
        # Check that we got the right number of results
        self.assertEqual(len(result), 2)
        
        # Check that the structure is correct
        self.assertEqual(result[0]['metricStat']['metric']['namespace'], 'AWS/DocDB')
        self.assertEqual(result[0]['metricStat']['metric']['metricName'], 'DatabaseConnectionsMax')
        self.assertEqual(result[0]['metricStat']['metric']['dimensions'][0]['name'], 'DBClusterIdentifier')
        self.assertEqual(result[0]['metricStat']['metric']['dimensions'][0]['value'], 'test-cluster-1')
        
        self.assertEqual(result[1]['metricStat']['metric']['dimensions'][0]['value'], 'test-cluster-2')
    
    def test_make_lists(self):
        """Test the make_lists method"""
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        # Split into chunks of 3
        result = self.cur_documentdbidlecost.make_lists(items, 3)
        
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], [1, 2, 3])
        self.assertEqual(result[1], [4, 5, 6])
        self.assertEqual(result[2], [7, 8, 9])
        self.assertEqual(result[3], [10])
    
    @patch('CostMinimizer.report_providers.cur_reports.reports.cur_documentdbidlecost.Cloudwatch')
    def test_process_check_data(self, mock_cloudwatch):
        """Test the process_check_data method"""
        # Mock the CloudWatch client
        mock_cw_instance = MagicMock()
        mock_cloudwatch.return_value = mock_cw_instance
        
        # Mock the CloudWatch response
        mock_cw_instance.get_metric_data.return_value = {
            'metricDataResults': [
                {
                    'id': 'id1',
                    'label': 'test-cluster-1',
                    'timestamps': [datetime.datetime.now(timezone.utc)],
                    'values': [0.0]  # Idle cluster
                },
                {
                    'id': 'id2',
                    'label': 'test-cluster-2',
                    'timestamps': [datetime.datetime.now(timezone.utc)],
                    'values': [10.0]  # Active cluster
                }
            ]
        }
        
        # Test data
        result = {
            'danteCallStatus': 'SUCCESSFUL',
            'dBClusters': [
                {
                    'dBClusterIdentifier': 'test-cluster-1',
                    'dBClusterMembers': ['instance-1'],
                    'dbClusterResourceId': 'resource-1'
                },
                {
                    'dBClusterIdentifier': 'test-cluster-2',
                    'dBClusterMembers': ['instance-2'],
                    'dbClusterResourceId': 'resource-2'
                }
            ]
        }
        
        # Call the method
        data_list = self.cur_documentdbidlecost.process_check_data('123456789012', 'us-east-1', None, result)
        
        # Check that we got only the idle cluster
        self.assertEqual(len(data_list), 1)
        self.assertEqual(data_list[0]['docdb_name'], 'test-cluster-1')
        self.assertEqual(data_list[0]['connection_count'], 0.0)
        self.assertEqual(data_list[0]['dbClusterResourceId'], 'resource-1')
    
    def test_sql(self):
        """Test the SQL query generation"""
        fqdb_name = "database.table"
        payer_id = "payer_id"
        account_id = "account_id"
        region = "us-east-1"
        max_date = "2023-01-01"
        
        result = self.cur_documentdbidlecost.sql(fqdb_name, payer_id, account_id, region, max_date)
        
        # Check that the query contains the expected elements
        self.assertIn("SELECT", result["query"])
        self.assertIn("FROM database.table", result["query"])
        self.assertIn("AmazonDocDB", result["query"])
        self.assertIn("line_item_usage_account_id", result["query"])
        self.assertIn("line_item_resource_id", result["query"])

if __name__ == '__main__':
    unittest.main()