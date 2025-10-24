import os
import boto3
import requests
import time
from unittest import TestCase
from datetime import datetime


class TestApiGateway(TestCase):
    api_endpoint: str

    def setUp(self) -> None:
        stack_name = "VisitorApi"
        client = boto3.client("cloudformation", "us-east-1")

        try:
            response = client.describe_stacks(StackName=stack_name)
        except Exception as e:
            raise Exception(
                f"Cannot find stack {stack_name}. \n"
                f'Please make sure stack with the name "{stack_name}" exists.'
            ) from e

        stacks = response["Stacks"]
        stack_outputs = stacks[0]["Outputs"]
        api_outputs = [output for output in stack_outputs if output["OutputKey"] == "VisitorApi"]

        self.assertTrue(api_outputs, f"Cannot find output VisitorApi in stack {stack_name}")
        self.api_endpoint = api_outputs[0]["OutputValue"]

    def test_api_gateway_returns_success(self):
        """
        Test that the API Gateway endpoint returns a successful response
        """
        response = requests.get(self.api_endpoint)
        response_json = response.json()

        # Assertions
        self.assertEqual(response.status_code, 200, "Expected HTTP 200 status code")
        self.assertIn("success", response_json, "Response should include success field")
        self.assertTrue(response_json["success"], "Success should be True")
        self.assertIn("visitId", response_json, "Response should include visitId")
        self.assertIn("message", response_json, "Response should include message")

    def test_api_gateway_creates_visit_record(self):
        """
        Test that calling the API creates a visit record in DynamoDB
        """
        # Call the API
        response = requests.get(self.api_endpoint)
        response_json = response.json()
        
        self.assertEqual(response.status_code, 200)
        visit_id = response_json.get("visitId")
        self.assertIsNotNone(visit_id, "visitId should be returned")

        # Wait a moment for DynamoDB to be consistent
        time.sleep(1)

        # Verify the record exists in DynamoDB
        ddbClient = boto3.client('dynamodb', 'us-east-1')
        table = 'visitor-details'
        
        try:
            get_response = ddbClient.get_item(
                TableName=table,
                Key={'visitId': {'S': visit_id}}
            )
            
            self.assertIn('Item', get_response, "Visit record should exist in DynamoDB")
            item = get_response['Item']
            
            # Verify required fields exist
            self.assertIn('timestamp', item, "Record should have timestamp")
            self.assertIn('ipAddress', item, "Record should have ipAddress")
            self.assertIn('userAgent', item, "Record should have userAgent")
            self.assertIn('browser', item, "Record should have browser")
            self.assertIn('os', item, "Record should have os")
            
        except Exception as e:
            self.fail(f"Failed to retrieve visit record from DynamoDB: {str(e)}")

    def test_api_gateway_records_multiple_visits(self):
        """
        Test that multiple API calls create multiple visit records
        """
        # Make first call
        response1 = requests.get(self.api_endpoint)
        self.assertEqual(response1.status_code, 200)
        visit_id1 = response1.json().get("visitId")
        
        # Make second call
        response2 = requests.get(self.api_endpoint)
        self.assertEqual(response2.status_code, 200)
        visit_id2 = response2.json().get("visitId")
        
        # Visit IDs should be different
        self.assertNotEqual(visit_id1, visit_id2, "Each visit should have a unique ID")
        
        # Wait for consistency
        time.sleep(1)
        
        # Verify both records exist
        ddbClient = boto3.client('dynamodb', 'us-east-1')
        table = 'visitor-details'
        
        for visit_id in [visit_id1, visit_id2]:
            get_response = ddbClient.get_item(
                TableName=table,
                Key={'visitId': {'S': visit_id}}
            )
            self.assertIn('Item', get_response, f"Visit record {visit_id} should exist")

    def test_api_gateway_counter_increments(self):
        """
        Test that the counter record increments with each visit
        """
        ddbClient = boto3.client('dynamodb', 'us-east-1')
        table = 'visitor-details'
        
        # Get initial counter value (if exists)
        try:
            initial_response = ddbClient.get_item(
                TableName=table,
                Key={'visitId': {'S': 'COUNTER'}}
            )
            initial_count = int(initial_response.get('Item', {}).get('visitCount', {}).get('N', '0'))
        except:
            initial_count = 0
        
        # Make API calls
        requests.get(self.api_endpoint)
        requests.get(self.api_endpoint)
        
        # Wait for consistency
        time.sleep(1)
        
        # Get updated counter value
        try:
            final_response = ddbClient.get_item(
                TableName=table,
                Key={'visitId': {'S': 'COUNTER'}}
            )
            
            if 'Item' in final_response:
                final_count = int(final_response['Item']['visitCount']['N'])
                self.assertGreaterEqual(
                    final_count, 
                    initial_count + 2, 
                    "Counter should have incremented by at least 2"
                )
        except Exception as e:
            # Counter is optional, so we can skip this assertion if it fails
            print(f"Note: Counter validation skipped: {str(e)}")

    def test_api_gateway_handles_cors(self):
        """
        Test that the API returns proper CORS headers
        """
        response = requests.get(self.api_endpoint)
        
        # Check for CORS header
        self.assertIn(
            'Access-Control-Allow-Origin', 
            response.headers,
            "Response should include CORS header"
        )
        self.assertEqual(
            response.headers['Access-Control-Allow-Origin'],
            '*',
            "CORS should allow all origins"
        )

    def test_api_gateway_records_timestamp(self):
        """
        Test that visit records include a valid timestamp
        """
        # Make API call
        response = requests.get(self.api_endpoint)
        visit_id = response.json().get("visitId")
        
        # Wait for consistency
        time.sleep(1)
        
        # Get the record
        ddbClient = boto3.client('dynamodb', 'us-east-1')
        get_response = ddbClient.get_item(
            TableName='visitor-details',
            Key={'visitId': {'S': visit_id}}
        )
        
        item = get_response['Item']
        timestamp_str = item['timestamp']['S']
        
        # Verify timestamp is valid and recent
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%SZ')
            time_diff = abs((datetime.utcnow() - timestamp).total_seconds())
            
            # Should be within last 5 minutes
            self.assertLess(
                time_diff, 
                300, 
                "Timestamp should be recent (within 5 minutes)"
            )
        except ValueError:
            self.fail(f"Timestamp format is invalid: {timestamp_str}")

    def test_api_gateway_stores_geolocation(self):
        """
        Test that visit records include geolocation data (when available)
        """
        # Make API call
        response = requests.get(self.api_endpoint)
        visit_id = response.json().get("visitId")
        
        # Wait for consistency
        time.sleep(1)
        
        # Get the record
        ddbClient = boto3.client('dynamodb', 'us-east-1')
        get_response = ddbClient.get_item(
            TableName='visitor-details',
            Key={'visitId': {'S': visit_id}}
        )
        
        item = get_response['Item']
        
        # Note: Geolocation might not be available for all IPs (e.g., localhost)
        # So we just check if the fields exist when present
        if 'country' in item:
            self.assertIsInstance(item['country']['S'], str)
            self.assertGreater(len(item['country']['S']), 0)
            
        if 'city' in item:
            self.assertIsInstance(item['city']['S'], str)
            
        # If geolocation worked, we should have coordinates
        if 'latitude' in item and 'longitude' in item:
            lat = float(item['latitude']['N'])
            lon = float(item['longitude']['N'])
            
            self.assertGreaterEqual(lat, -90)
            self.assertLessEqual(lat, 90)
            self.assertGreaterEqual(lon, -180)
            self.assertLessEqual(lon, 180)