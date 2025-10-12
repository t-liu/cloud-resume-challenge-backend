import os
import json
import logging
from datetime import datetime
from typing import Dict, Any
import boto3
import botocore

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

"""
Note: There is only one record in this DynamoDB table 
that holds a primary key of 1, the last viewed 
date in string format, and the total view count.
"""

# Initialize DynamoDB client
region = os.environ.get('AWS_REGION', 'us-east-1')
ddbClient = boto3.client('dynamodb', region_name=region)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler that retrieves the previous last viewed date,
    increments visitor count, and updates last viewed date.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response with visitor data including previous and new last viewed date
    """
    ddb_table_name = os.environ.get('tableName')
    ddb_partition_key = os.environ.get('partitionKey')
    
    # Validate environment variables
    if not ddb_table_name or not ddb_partition_key:
        logger.error("Missing required environment variables: tableName or partitionKey")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Internal server error"}),
            "isBase64Encoded": False
        }
    
    try:
        # Step 1: Retrieve the current record to get the previous lastViewedDate
        response_get = ddbClient.get_item(
            TableName=ddb_table_name,
            Key={ddb_partition_key: {"N": "1"}},
            ProjectionExpression='lastViewedDate, vc'  # Fetch only needed attributes
        )
        
        # Extract previous last viewed date (handle case where item doesn't exist)
        previous_last_viewed = None
        item = response_get.get('Item')
        if item and 'lastViewedDate' in item:
            previous_last_viewed = item['lastViewedDate'].get('S')
        
        logger.info(f"Retrieved previous last viewed date: {previous_last_viewed}")
        
        # Step 2: Update the record
        now = datetime.now()
        response_update = ddbClient.update_item(
            TableName=ddb_table_name,
            Key={ddb_partition_key: {"N": "1"}},
            UpdateExpression='ADD vc :incr SET lastViewedDate = :ts',
            ExpressionAttributeValues={
                ':incr': {"N": "1"},
                ':ts': {"S": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
            },
            ReturnValues='ALL_NEW'
        )
        
        logger.info(f"Successfully updated visitor data: {response_update}")
        
        item = response_update.get('Attributes', {})
        
        # Step 3: Return both the previous and new last viewed date
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "previousLastViewed": previous_last_viewed,  # Previous date
                "lastViewed": item.get('lastViewedDate', {}).get('S'),  # New date
                "count": item.get('vc', {}).get('N')  # Updated count
            }),
            "isBase64Encoded": False
        }
        
    except botocore.exceptions.ClientError as e:
        logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Failed to process visitor data"}),
            "isBase64Encoded": False
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "Internal server error"}),
            "isBase64Encoded": False
        }