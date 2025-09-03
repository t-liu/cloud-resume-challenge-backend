import os
import boto3
import requests
from unittest import TestCase
from datetime import datetime
from datetime import date

class TestApiGateway(TestCase):
    api_endpoint: str

    def setUp(self) -> None:

        stack_name = "VisitorApi"
        client = boto3.client("cloudformation", "us-east-1")

        try:
            response = client.describe_stacks(StackName=stack_name)
        except Exception as e:
            raise Exception(
                f"Cannot find stack {stack_name}. \n" f'Please make sure stack with the name "{stack_name}" exists.'
            ) from e

        stacks = response["Stacks"]

        stack_outputs = stacks[0]["Outputs"]
        api_outputs = [output for output in stack_outputs if output["OutputKey"] == "VisitorApi"]
        
        self.assertTrue(api_outputs, f"Cannot find output VisitorApi in stack {stack_name}")
        self.api_endpoint = api_outputs[0]["OutputValue"]

    def test_api_gateway(self):
        
        # update table with a date to prevent error
        ddbClient = boto3.client('dynamodb','us-east-1')
        table = 'visitors'
        pk = 'visitorId'
        column = 'lastViewedDate'
        now = datetime.now()

        response = ddbClient.update_item(
            TableName=table,
            Key={pk: {"N": "1"}},
            UpdateExpression='SET ' + column + ' = :ts',
            ExpressionAttributeValues={
                ':ts': {"S": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
            }
        )

        """
        Call the API Gateway endpoint and check the response
        """
        response = requests.get(self.api_endpoint)
        responseLastViewedAsDate = datetime.strptime(response.json()["lastViewed"]["S"], '%Y-%m-%dT%H:%M:%SZ').date()

        self.assertGreaterEqual(int(response.json()["count"]["N"]), 1)        
        self.assertEqual(responseLastViewedAsDate, datetime.utcnow().date())
