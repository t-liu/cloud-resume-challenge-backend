import os
import json
import string
import boto3
from datetime import datetime

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
    if 'Item' in response:
        # return response['Item'][column]
        print(response)
    else:
        # return {'statusCode': '404', 'body': 'Not Found'}
        print ('No items')

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
    return(response)   

def get_visitor_count(table, pk, column):
    
    response = ddbClient.get_item(
            TableName=table,
            Key={pk: {"N": "1"}}
        )
    if 'Item' in response:
        return response['Item'][column]
    else:
        return {
            'statusCode': '404',
            'body': 'Not Found'
        }
        
def get_last_viewed_date(table, pk, column):
    
    response = ddbClient.get_item(
            TableName=table,
            Key={pk: {"N": "1"}}
        )
    if 'Item' in response:
        return response['Item'][column]
    else:
        return {
            'statusCode': '404',
            'body': 'Not Found'
        }

def lambda_handler(event, context):

    ddbTableName = os.environ['tableName']
    
    # get last viewed date and store to response date var
    responseLastViewedDate = get_last_viewed_date(ddbTableName, 'visitorId', 'lastViewedDate')
    
    # update visitor count & last viewed date
    update_visitor_count(ddbTableName, 'visitorId', 'vc')
    update_last_viewed_date(ddbTableName, 'visitorId', 'lastViewedDate')
    
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
            "count": get_visitor_count(ddbTableName, 'visitorId', 'vc')
        }),
        "isBase64Encoded": "false"
    } 