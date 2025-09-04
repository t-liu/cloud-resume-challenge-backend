import os
import sys
import json
import boto3
import pytest
from moto import mock_dynamodb
from datetime import datetime
from datetime import date

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

@pytest.fixture()
def apigw_event():
    """ Generates AWS API Gateway Event"""

    return {
        "body": '{ "test": "body"}',
        "resource": "/{proxy+}",
        "requestContext": {
            "resourceId": "123456",
            "apiId": "1234567890",
            "resourcePath": "/{proxy+}",
            "httpMethod": "GET",
            "requestId": "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
            "accountId": "123456789012",
            "identity": {
                "apiKey": "",
                "userArn": "",
                "cognitoAuthenticationType": "",
                "caller": "",
                "userAgent": "Custom User Agent String",
                "user": "",
                "cognitoIdentityPoolId": "",
                "cognitoIdentityId": "",
                "cognitoAuthenticationProvider": "",
                "sourceIp": "127.0.0.1",
                "accountId": "",
            },
            "stage": "Prod",
        },
        "headers": {
            "Via": "1.1 08f323deadbeefa7af34d5feb414ce27.cloudfront.net (CloudFront)",
            "Accept-Language": "en-US,en;q=0.8",
            "CloudFront-Is-Desktop-Viewer": "true",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Is-Mobile-Viewer": "false",
            "X-Forwarded-For": "127.0.0.1, 127.0.0.2",
            "CloudFront-Viewer-Country": "US",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "X-Forwarded-Port": "443",
            "Host": "1234567890.execute-api.us-east-1.amazonaws.com",
            "X-Forwarded-Proto": "https",
            "X-Amz-Cf-Id": "aaaaaaaaaae3VYQb9jd-nvCd-de396Uhbp027Y2JvkCPNLmGJHqlaA==",
            "CloudFront-Is-Tablet-Viewer": "false",
            "Cache-Control": "max-age=0",
            "User-Agent": "Custom User Agent String",
            "CloudFront-Forwarded-Proto": "https",
            "Accept-Encoding": "gzip, deflate, sdch",
        },
        "pathParameters": {"proxy": "/visitor"},
        "httpMethod": "GET",
        "path": "/visitor",
    }

@mock_dynamodb
def test_update_visitor_count(apigw_event):
    """
    script for lambda function already establishs a boto3 client when imported
    therefore mock could not break that hence the import inside the function
    """
    import visitor.app 
    
    # Create mock dynamodb table
    table_name = 'visitor_test'
    partition_key = 'visitorId1'
    data_field = 'vc'
    
    dynamodb = boto3.client('dynamodb','us-east-1')

    table = dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': partition_key,'AttributeType': 'N'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': partition_key, 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # update table
    ret = visitor.app.update_visitor_count(table_name, partition_key, data_field)
    
    response = dynamodb.get_item(
            TableName=table_name,
            Key={partition_key: {"N": "1"}}
        )

    item = response['Item']
    assert int(item[data_field]['N']) == 1


@mock_dynamodb
def test_update_last_viewed_date(apigw_event):

    import visitor.app 
    
    # Create mock dynamodb table
    table_name = 'visitor_test2'
    partition_key = 'visitorId2'
    data_field = 'lastViewedDate'
    
    dynamodb = boto3.client('dynamodb','us-east-1')

    table = dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': partition_key,'AttributeType': 'N'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': partition_key, 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # update table
    ret = visitor.app.update_last_viewed_date(table_name, partition_key, data_field)
    
    response = dynamodb.get_item(
            TableName=table_name,
            Key={partition_key: {"N": "1"}}
        )

    item = response['Item']
    assert datetime.strptime(item[data_field]['S'], '%Y-%m-%dT%H:%M:%SZ').date() == date.today()

@mock_dynamodb
def test_get_data(apigw_event):

    import visitor.app 
    
    # Create mock dynamodb table
    table_name = 'visitor_test3'
    partition_key = 'visitorId'
    count_field = 'vc'
    date_field = 'lastViewedDate'
    
    dynamodb = boto3.client('dynamodb','us-east-1')

    table = dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': partition_key,'AttributeType': 'N'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': partition_key, 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # insert test data in table via boto3
    dynamodb.put_item(
        TableName=table_name, 
        Item={
            partition_key:{'N': "1"}, 
            date_field:{'S': '2022-02-15T00:00:00Z'}, 
            count_field:{'N': "100"}
        }
    )

    responseCount = visitor.app.get_visitor_data(table_name, partition_key, count_field)
    assert int(responseCount['N']) == 100

    responseDate = visitor.app.get_visitor_data(table_name, partition_key, date_field)
    assert responseDate['S'] == "2022-02-15T00:00:00Z"

@pytest.fixture
def test_get_env_vars_with_monkeypatch(monkeypatch):
    monkeypatch.setenv('tableName', 'visitor_test_main')
    monkeypatch.setenv('partitionKey', 'visitorMainId')

@mock_dynamodb
def test_main_handler(apigw_event, test_get_env_vars_with_monkeypatch):

    import visitor.app 
    
    # Create mock dynamodb table with monkey patch env vars
    table_name = os.environ['tableName']
    partition_key = os.environ['partitionKey']
    
    dynamodb = boto3.client('dynamodb','us-east-1')

    table = dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': partition_key,'AttributeType': 'N'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': partition_key, 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # update dynamodb with date first then call main lambda handler
    visitor.app.update_last_viewed_date(table_name, partition_key, 'lastViewedDate')
    response = visitor.app.lambda_handler(apigw_event, "")
   
    assert response["statusCode"] == 200
    assert "count" in response["body"]
    assert "lastViewed" in response["body"]

    responseBody = json.loads(response["body"])
    assert int(responseBody["count"]["N"]) == 1
    assert datetime.strptime(responseBody["lastViewed"]["S"], '%Y-%m-%dT%H:%M:%SZ').date() == date.today()

    # make second call to lambda handler
    response2 = visitor.app.lambda_handler(apigw_event, "")

    assert response2["statusCode"] == 200
    responseBody2 = json.loads(response2["body"])
    assert int(responseBody2["count"]["N"]) == 2