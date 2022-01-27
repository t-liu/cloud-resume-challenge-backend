import os
import json
import string
import boto3
from datetime import datetime

# NOTE: there is only one record in this dynamodb table 
#       that holds a primary key of 1, the last viewed 
#       date in string format, and the total view count

ddbClient = boto3.client('dynamodb')

def updateVisitorCount(table, pk, column, column2):

    now = datetime.now()
    response = ddbClient.update_item(
        TableName=table,
        Key={pk: {"N": "1"}},
        UpdateExpression='ADD ' + column + ' :incr SET ' + column2 + ' = :ts',
        ExpressionAttributeValues={
            ':incr': {"N": "1"},
            ':ts': {"S": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        }
    )
    print(response)

def getVisitorCount(table, pk, column):
    
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
        
def getLastViewedDate(table, pk, column):
    
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

def main(event, context):
    
    # get last viewed date and store to response date var
    responseLastViewedDate = getLastViewedDate(os.environ['tableName'], 'visitorId', 'lastViewedDate')
    
    # update visitor count
    updateVisitorCount(os.environ['tableName'], 'visitorId', 'vc', 'lastViewedDate')
    
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
            "count": getVisitorCount(os.environ['tableName'], 'visitorId', 'vc')
        }),
        "isBase64Encoded": "false"
    } 