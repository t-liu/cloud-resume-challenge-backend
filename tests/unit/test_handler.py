import os
import json
import boto3
import pytest
from moto import mock_dynamodb2
import visitor.app


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

@mock_dynamodb2
def test_main(apigw_event):

    # Create mock dynamodb table
    table_name = 'visitors'
    partition_key = 'visitorId'
    
    dynamodb = boto3.client('dynamodb')

    table = dynamodb.create_table(
        AttributeDefinitions=[{'AttributeName': partition_key,'AttributeType': 'N'}],
        TableName=table_name,
        KeySchema=[{'AttributeName': partition_key, 'KeyType': 'HASH'}],
        TableClass='STANDARD',
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    
    # update table
    ret = visitor.app.update_visitor_count(table_name, partition_key, 'vc')
    
    response = dynamodb.get_item(
            TableName=table_name,
            Key={partition_key: {"N": "1"}}
        )

    #print("test")
    #print(response)
    item = response['Item']
    assert item['vc'] == 1
  