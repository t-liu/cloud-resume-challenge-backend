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
# In Lambda, AWS_REGION is automatically set; for local testing, default to us-east-1
region = os.environ.get('AWS_REGION', 'us-east-1')
ddbClient = boto3.client('dynamodb', region_name=region)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler that increments visitor count and updates last viewed date.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response with visitor data
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
        now = datetime.now()
        
        # Single optimized DynamoDB operation that:
        # 1. Increments visitor count
        # 2. Updates last viewed date
        # 3. Returns all updated values
        response = ddbClient.update_item(
            TableName=ddb_table_name,
            Key={ddb_partition_key: {"N": "1"}},
            UpdateExpression='ADD vc :incr SET lastViewedDate = :ts',
            ExpressionAttributeValues={
                ':incr': {"N": "1"},
                ':ts': {"S": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
            },
            ReturnValues='ALL_NEW'
        )
        
        logger.info(f"Successfully updated visitor data: {response}")
        
        item = response.get('Attributes', {})
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "lastViewed": item.get('lastViewedDate'),
                "count": item.get('vc')
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
            "body": json.dumps({"error": "Failed to update visitor data"}),
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