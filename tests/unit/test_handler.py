import os
import sys
import json
import boto3
import pytest
from moto import mock_dynamodb
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


@pytest.fixture()
def apigw_event():
    """Generates AWS API Gateway Event"""
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


@pytest.fixture
def set_env_vars(monkeypatch):
    """Set environment variables for tests"""
    monkeypatch.setenv('tableName', 'visitor_test')
    monkeypatch.setenv('partitionKey', 'visitorId')


@mock_dynamodb
def test_lambda_handler_first_visit(apigw_event, set_env_vars):
    """Test lambda handler on first visit (creates new entry)"""
    import visitor.app
    
    # Create mock DynamoDB table
    table_name = os.environ['tableName']
    partition_key = os.environ['partitionKey']
    
    dynamodb = boto3.client('dynamodb', 'us-east-1')
    
    dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': partition_key, 'AttributeType': 'N'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': partition_key, 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # Call lambda handler
    response = visitor.app.lambda_handler(apigw_event, "")
    
    # Verify response structure
    assert response["statusCode"] == 200
    assert "Content-Type" in response["headers"]
    assert response["isBase64Encoded"] is False
    
    # Verify response body
    response_body = json.loads(response["body"])
    assert "count" in response_body
    assert "lastViewed" in response_body
    assert "previousLastViewed" in response_body
    
    # Verify count is 1 on first visit
    assert response_body["count"] == "1"
    
    # Verify previousLastViewed is None on first visit
    assert response_body["previousLastViewed"] is None
    
    # Verify date format for lastViewed
    assert response_body["lastViewed"]
    datetime.strptime(response_body["lastViewed"], '%Y-%m-%dT%H:%M:%SZ')


@mock_dynamodb
def test_lambda_handler_multiple_visits(apigw_event, set_env_vars):
    """Test lambda handler increments count on multiple visits"""
    import visitor.app
    
    # Create mock DynamoDB table
    table_name = os.environ['tableName']
    partition_key = os.environ['partitionKey']
    
    dynamodb = boto3.client('dynamodb', 'us-east-1')
    
    dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': partition_key, 'AttributeType': 'N'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': partition_key, 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # Make first call
    response1 = visitor.app.lambda_handler(apigw_event, "")
    assert response1["statusCode"] == 200
    response_body1 = json.loads(response1["body"])
    assert response_body1["count"] == "1"
    assert response_body1["previousLastViewed"] is None
    first_visit_date = response_body1["lastViewed"]
    
    # Make second call
    response2 = visitor.app.lambda_handler(apigw_event, "")
    assert response2["statusCode"] == 200
    response_body2 = json.loads(response2["body"])
    assert response_body2["count"] == "2"
    assert response_body2["previousLastViewed"] == first_visit_date
    
    # Make third call
    response3 = visitor.app.lambda_handler(apigw_event, "")
    assert response3["statusCode"] == 200
    response_body3 = json.loads(response3["body"])
    assert response_body3["count"] == "3"
    assert response_body3["previousLastViewed"] == response_body2["lastViewed"]


@mock_dynamodb
def test_lambda_handler_existing_data(apigw_event, set_env_vars):
    """Test lambda handler with existing visitor data"""
    import visitor.app
    
    # Create mock DynamoDB table
    table_name = os.environ['tableName']
    partition_key = os.environ['partitionKey']
    
    dynamodb = boto3.client('dynamodb', 'us-east-1')
    
    dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': partition_key, 'AttributeType': 'N'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': partition_key, 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # Insert existing data
    existing_date = '2024-01-01T00:00:00Z'
    dynamodb.put_item(
        TableName=table_name,
        Item={
            partition_key: {'N': "1"},
            'lastViewedDate': {'S': existing_date},
            'vc': {'N': "100"}
        }
    )
    
    # Call lambda handler
    response = visitor.app.lambda_handler(apigw_event, "")
    
    assert response["statusCode"] == 200
    response_body = json.loads(response["body"])
    
    # Count should be incremented to 101
    assert response_body["count"] == "101"
    
    # Previous last viewed date should match the existing date
    assert response_body["previousLastViewed"] == existing_date
    
    # New date should be different from the existing date
    assert response_body["lastViewed"] != existing_date
    
    # Verify new date format
    datetime.strptime(response_body["lastViewed"], '%Y-%m-%dT%H:%M:%SZ')


def test_lambda_handler_missing_env_vars(apigw_event, monkeypatch):
    """Test lambda handler handles missing environment variables"""
    import visitor.app
    
    # Unset environment variables
    monkeypatch.delenv('tableName', raising=False)
    monkeypatch.delenv('partitionKey', raising=False)
    
    response = visitor.app.lambda_handler(apigw_event, "")
    
    # Should return 500 error
    assert response["statusCode"] == 500
    response_body = json.loads(response["body"])
    assert "error" in response_body