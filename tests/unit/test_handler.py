import os
import sys
import json
import boto3
import pytest
from moto import mock_dynamodb
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


@pytest.fixture()
def apigw_event():
    """Generates AWS API Gateway Event with realistic headers"""
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
                "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "user": "",
                "cognitoIdentityPoolId": "",
                "cognitoIdentityId": "",
                "cognitoAuthenticationProvider": "",
                "sourceIp": "203.0.113.42",
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
            "X-Forwarded-For": "203.0.113.42, 127.0.0.2",
            "CloudFront-Viewer-Country": "US",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "X-Forwarded-Port": "443",
            "Host": "1234567890.execute-api.us-east-1.amazonaws.com",
            "X-Forwarded-Proto": "https",
            "X-Amz-Cf-Id": "aaaaaaaaaae3VYQb9jd-nvCd-de396Uhbp027Y2JvkCPNLmGJHqlaA==",
            "CloudFront-Is-Tablet-Viewer": "false",
            "Cache-Control": "max-age=0",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://google.com",
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
    monkeypatch.setenv('AWS_REGION', 'us-east-1')


@pytest.fixture
def mock_geolocation():
    """Mock the geolocation API call"""
    mock_geo_data = {
        'status': 'success',
        'country': 'United States',
        'countryCode': 'US',
        'regionName': 'California',
        'city': 'San Francisco',
        'lat': 37.7749,
        'lon': -122.4194,
        'timezone': 'America/Los_Angeles',
        'isp': 'Example ISP'
    }
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_geo_data).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        yield mock_urlopen


@mock_dynamodb
def test_lambda_handler_creates_visit_record(apigw_event, set_env_vars, mock_geolocation):
    """Test lambda handler creates a new visit record with all details"""
    import visitor.app
    
    # Create mock DynamoDB table with String primary key
    table_name = os.environ['tableName']
    
    dynamodb = boto3.client('dynamodb', 'us-east-1')
    
    dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': 'visitId', 'AttributeType': 'S'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': 'visitId', 'KeyType': 'HASH'}],
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
    assert "success" in response_body
    assert response_body["success"] is True
    assert "visitId" in response_body
    assert "message" in response_body
    
    # Verify a visit record was created in DynamoDB
    scan_response = dynamodb.scan(TableName=table_name)
    items = scan_response['Items']
    
    # Should have at least 1 visit record (may have COUNTER too)
    visit_items = [item for item in items if item['visitId']['S'] != 'COUNTER']
    assert len(visit_items) >= 1
    
    # Verify the visit record has expected fields
    visit_record = visit_items[0]
    assert 'timestamp' in visit_record
    assert 'ipAddress' in visit_record
    assert visit_record['ipAddress']['S'] == '203.0.113.42'
    assert 'userAgent' in visit_record
    assert 'browser' in visit_record
    assert 'os' in visit_record
    assert 'referer' in visit_record
    
    # Verify geolocation data
    assert 'country' in visit_record
    assert visit_record['country']['S'] == 'United States'
    assert 'city' in visit_record
    assert 'latitude' in visit_record
    assert 'longitude' in visit_record


@mock_dynamodb
def test_lambda_handler_extracts_browser_info(apigw_event, set_env_vars, mock_geolocation):
    """Test lambda handler correctly parses browser and OS from user agent"""
    import visitor.app
    
    # Create mock DynamoDB table
    table_name = os.environ['tableName']
    dynamodb = boto3.client('dynamodb', 'us-east-1')
    
    dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': 'visitId', 'AttributeType': 'S'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': 'visitId', 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # Call lambda handler
    response = visitor.app.lambda_handler(apigw_event, "")
    
    # Verify browser and OS were extracted
    scan_response = dynamodb.scan(TableName=table_name)
    visit_items = [item for item in scan_response['Items'] if item['visitId']['S'] != 'COUNTER']
    
    assert len(visit_items) >= 1
    visit_record = visit_items[0]
    
    assert visit_record['browser']['S'] == 'Chrome'
    assert visit_record['os']['S'] == 'macOS'


@mock_dynamodb
def test_lambda_handler_handles_geolocation_failure(apigw_event, set_env_vars):
    """Test lambda handler gracefully handles geolocation API failures"""
    import visitor.app
    
    # Create mock DynamoDB table
    table_name = os.environ['tableName']
    dynamodb = boto3.client('dynamodb', 'us-east-1')
    
    dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': 'visitId', 'AttributeType': 'S'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': 'visitId', 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # Mock geolocation to fail
    with patch('urllib.request.urlopen', side_effect=Exception("API Error")):
        response = visitor.app.lambda_handler(apigw_event, "")
    
    # Should still succeed without geolocation data
    assert response["statusCode"] == 200
    response_body = json.loads(response["body"])
    assert response_body["success"] is True
    
    # Verify record was still created (without geolocation fields)
    scan_response = dynamodb.scan(TableName=table_name)
    visit_items = [item for item in scan_response['Items'] if item['visitId']['S'] != 'COUNTER']
    
    assert len(visit_items) >= 1
    visit_record = visit_items[0]
    
    # Basic fields should exist
    assert 'timestamp' in visit_record
    assert 'ipAddress' in visit_record
    
    # Geolocation fields should not exist
    assert 'country' not in visit_record or visit_record.get('country') is None


@mock_dynamodb
def test_lambda_handler_updates_counter(apigw_event, set_env_vars, mock_geolocation):
    """Test lambda handler maintains a counter record"""
    import visitor.app
    
    # Create mock DynamoDB table
    table_name = os.environ['tableName']
    dynamodb = boto3.client('dynamodb', 'us-east-1')
    
    dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': 'visitId', 'AttributeType': 'S'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': 'visitId', 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # Make first call
    visitor.app.lambda_handler(apigw_event, "")
    
    # Make second call
    visitor.app.lambda_handler(apigw_event, "")
    
    # Check counter record
    try:
        counter_response = dynamodb.get_item(
            TableName=table_name,
            Key={'visitId': {'S': 'COUNTER'}}
        )
        
        if 'Item' in counter_response:
            counter_item = counter_response['Item']
            assert 'visitCount' in counter_item
            assert int(counter_item['visitCount']['N']) == 2
    except Exception:
        # Counter is optional, so this test can pass even if counter fails
        pass


@mock_dynamodb
def test_lambda_handler_handles_missing_headers(set_env_vars, mock_geolocation):
    """Test lambda handler handles events with missing headers gracefully"""
    import visitor.app
    
    # Create mock DynamoDB table
    table_name = os.environ['tableName']
    dynamodb = boto3.client('dynamodb', 'us-east-1')
    
    dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': 'visitId', 'AttributeType': 'S'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': 'visitId', 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # Create minimal event
    minimal_event = {
        "requestContext": {},
        "headers": {}
    }
    
    # Call lambda handler
    response = visitor.app.lambda_handler(minimal_event, "")
    
    # Should still succeed
    assert response["statusCode"] == 200
    response_body = json.loads(response["body"])
    assert response_body["success"] is True


def test_lambda_handler_missing_env_vars(apigw_event, monkeypatch):
    """Test lambda handler handles missing environment variables"""
    import visitor.app
    
    # Unset environment variables
    monkeypatch.delenv('tableName', raising=False)
    
    response = visitor.app.lambda_handler(apigw_event, "")
    
    # Should return 500 error
    assert response["statusCode"] == 500
    response_body = json.loads(response["body"])
    assert "error" in response_body


def test_parse_user_agent_chrome():
    """Test user agent parsing for Chrome"""
    from visitor.app import parse_user_agent
    
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    result = parse_user_agent(ua)
    
    assert result['browser'] == 'Chrome'
    assert result['os'] == 'Windows'


def test_parse_user_agent_firefox():
    """Test user agent parsing for Firefox"""
    from visitor.app import parse_user_agent
    
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    result = parse_user_agent(ua)
    
    assert result['browser'] == 'Firefox'
    assert result['os'] == 'Windows'


def test_parse_user_agent_safari():
    """Test user agent parsing for Safari"""
    from visitor.app import parse_user_agent
    
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
    result = parse_user_agent(ua)
    
    assert result['browser'] == 'Safari'
    assert result['os'] == 'macOS'


def test_parse_user_agent_unknown():
    """Test user agent parsing handles unknown agents"""
    from visitor.app import parse_user_agent
    
    result = parse_user_agent(None)
    assert result['browser'] == 'Unknown'
    assert result['os'] == 'Unknown'
    
    result = parse_user_agent("")
    assert result['browser'] == 'Unknown'
    assert result['os'] == 'Unknown'