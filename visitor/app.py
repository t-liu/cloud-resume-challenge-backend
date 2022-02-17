import os
import json
import string
import boto3
from datetime import datetime
import botocore

"""
note: there is only one record in this dynamodb table 
       that holds a primary key of 1, the last viewed 
       date in string format, and the total view count
"""

ddbClient = boto3.client('dynamodb','us-east-1')

def update_visitor_count(table, pk, column):

    response = ddbClient.update_item(
        TableName=table,
        Key={pk: {"N": "1"}},
        UpdateExpression='ADD ' + column + ' :incr',
        ExpressionAttributeValues={
            ':incr': {"N": "1"}
        }
    )
    print(response)
    if 'Item' in response: 
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response)
        }
        # return response['Item'][column]
    else:
        return {
            "statusCode": 404,
            "headers": {
                "Access-Control-Allow-Origin": "*"
            },
            "body": "Not Found"
        }

def update_last_viewed_date(table, pk, column):

    now = datetime.now()
    response = ddbClient.update_item(
        TableName=table,
        Key={pk: {"N": "1"}},
        UpdateExpression='SET ' + column + ' = :ts',
        ExpressionAttributeValues={
            ':ts': {"S": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        }
    )
    print(response)
    if 'Item' in response:        
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response)
        }
        # return response['Item'][column]
    else:
        return {
            "statusCode": 404,
            "headers": {
                "Access-Control-Allow-Origin": "*"
            },
            "body": "Not Found"
        }  

def get_visitor_data(table, pk, column):
    
    try:
        response = ddbClient.get_item(
            TableName=table,
            Key={pk: {"N": "1"}}
        )
    except botocore.exceptions.ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print(response)

    if 'Item' in response:
        return response['Item'][column]
    else:
        return {
            'statusCode': '404',
            'body': 'Not Found'
        }

def lambda_handler(event, context):

    ddbTableName = os.environ['tableName']
    ddbPartitionKey = os.environ['partitionKey']
    
    # get last viewed date and store to response date var
    responseLastViewedDate = get_visitor_data(ddbTableName, ddbPartitionKey, 'lastViewedDate')
    
    # update visitor count & last viewed date
    update_visitor_count(ddbTableName, ddbPartitionKey, 'vc')
    update_last_viewed_date(ddbTableName, ddbPartitionKey, 'lastViewedDate')
    
    # api gateway requires all four keys in the return when using lambda proxy integration
    # body must be stringify hence the json dumps
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({
            "lastViewed": responseLastViewedDate,
            "count": get_visitor_data(ddbTableName, ddbPartitionKey, 'vc')
        }),
        "isBase64Encoded": "false"
    } 