import os
import json
import logging
from datetime import datetime
import boto3
import botocore
import urllib.request
import urllib.error
from uuid import uuid4

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
region = os.environ.get('AWS_REGION', 'us-east-1')
ddbClient = boto3.client('dynamodb', region_name=region)

def get_geolocation(ip_address):

    if not ip_address or ip_address == '127.0.0.1':
        return None
        
    try:
        url = f"http://ip-api.com/json/{ip_address}?fields=status,country,countryCode,region,regionName,city,lat,lon,timezone,isp"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            if data.get('status') == 'success':
                return {
                    'country': data.get('country'),
                    'countryCode': data.get('countryCode'),
                    'region': data.get('regionName'),
                    'city': data.get('city'),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'timezone': data.get('timezone'),
                    'isp': data.get('isp')
                }
    except Exception as e:
        logger.warning(f"Failed to get geolocation for {ip_address}: {str(e)}")
    
    return None

def parse_user_agent(user_agent):

    if not user_agent:
        return {'browser': 'Unknown', 'os': 'Unknown'}
    
    # Simple browser detection
    browser = 'Unknown'
    if 'Edg/' in user_agent:
        browser = 'Edge'
    elif 'Chrome/' in user_agent:
        browser = 'Chrome'
    elif 'Firefox/' in user_agent:
        browser = 'Firefox'
    elif 'Safari/' in user_agent and 'Chrome' not in user_agent:
        browser = 'Safari'
    
    # Simple OS detection
    os_name = 'Unknown'
    if 'Windows' in user_agent:
        os_name = 'Windows'
    elif 'Macintosh' in user_agent or 'Mac OS X' in user_agent:
        os_name = 'macOS'
    elif 'Linux' in user_agent:
        os_name = 'Linux'
    elif 'Android' in user_agent:
        os_name = 'Android'
    elif 'iPhone' in user_agent or 'iPad' in user_agent:
        os_name = 'iOS'
    
    return {'browser': browser, 'os': os_name}

def get_next_visit_number(table_name, starting_number=1):

    current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    try:
        response = ddbClient.update_item(
            TableName=table_name,
            Key={'visitId': {'S': 'COUNTER'}},
            UpdateExpression='ADD visitCount :incr SET lastUpdated = :ts',
            ExpressionAttributeValues={
                ':incr': {'N': '1'},
                ':ts': {'S': current_timestamp}
            },
            ReturnValues='ALL_OLD'
        )
        
        # Get the previous lastUpdated (before this update)
        previous_last_updated = None
        if 'Attributes' in response and 'lastUpdated' in response['Attributes']:
            previous_last_updated = response['Attributes']['lastUpdated']['S']
        
        # Get the new count (we need to add 1 to the old count since we used ALL_OLD)
        if 'Attributes' in response and 'visitCount' in response['Attributes']:
            visit_number = int(response['Attributes']['visitCount']['N']) + 1
        else:
            visit_number = starting_number
        
        logger.info(f"Incremented counter to: {visit_number}, previous update: {previous_last_updated}")
        return visit_number, previous_last_updated
        
    except botocore.exceptions.ClientError as e:
        error_code = e.response['Error']['Code']
        
        # If item doesn't exist, create it with starting_number
        if error_code == 'ValidationException' or 'Item' not in str(e):
            logger.info(f"COUNTER doesn't exist, initializing with {starting_number}")
            try:
                # Initialize counter
                ddbClient.put_item(
                    TableName=table_name,
                    Item={
                        'visitId': {'S': 'COUNTER'},
                        'visitCount': {'N': str(starting_number)},
                        'lastUpdated': {'S': datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")}
                    },
                    ConditionExpression='attribute_not_exists(visitId)'  # Only if doesn't exist
                )
                return starting_number, None
            except botocore.exceptions.ClientError as create_error:
                # If another Lambda created it simultaneously, try to get it
                if create_error.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    logger.warning("COUNTER was created by another request, retrying...")
                    return get_next_visit_number(table_name, starting_number)
                else:
                    logger.error(f"Failed to initialize counter: {str(create_error)}")
                    # Return a fallback number
                    return starting_number, None
        else:
            logger.error(f"Failed to get visit number: {str(e)}")
            # Return a fallback number based on timestamp
            return starting_number + int(datetime.now().timestamp() % 1000), None

def lambda_handler(event: dict, context: any) -> dict:

    ddb_table_name = os.environ.get('tableName')
    starting_visit_number = int(os.environ.get('startingVisitNumber', '1'))
    
    # Validate environment variables
    if not ddb_table_name:
        logger.error("Missing required environment variable: tableName")
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
        # Get next sequential visit number
        visit_num_id, previous_last_updated = get_next_visit_number(ddb_table_name, starting_visit_number)
        
        # Extract request information from API Gateway event
        request_context = event.get('requestContext', {})
        headers = event.get('headers', {})
        
        # Get IP address (check multiple possible locations)
        ip_address = (
            headers.get('X-Forwarded-For', '').split(',')[0].strip() or
            headers.get('x-forwarded-for', '').split(',')[0].strip() or
            request_context.get('identity', {}).get('sourceIp') or
            'Unknown'
        )
        
        # Get user agent
        user_agent = headers.get('User-Agent') or headers.get('user-agent', 'Unknown')
        
        # Parse browser and OS
        browser_info = parse_user_agent(user_agent)
        
        # Get geolocation
        geo_data = get_geolocation(ip_address)
        
        # Get referer
        referer = headers.get('Referer') or headers.get('referer', 'Direct')
        
        # Create timestamp and unique ID
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        visit_id = str(uuid4())
        
        # Prepare DynamoDB item
        item = {
            'visitId': {'S': visit_id},
            'visitNumId': {'N': str(visit_num_id)},  # Sequential counter
            'timestamp': {'S': timestamp},
            'ipAddress': {'S': ip_address},
            'userAgent': {'S': user_agent},
            'browser': {'S': browser_info['browser']},
            'os': {'S': browser_info['os']},
            'referer': {'S': referer}
        }
        
        # Add geolocation data if available
        if geo_data:
            if geo_data.get('country'):
                item['country'] = {'S': geo_data['country']}
            if geo_data.get('countryCode'):
                item['countryCode'] = {'S': geo_data['countryCode']}
            if geo_data.get('region'):
                item['region'] = {'S': geo_data['region']}
            if geo_data.get('city'):
                item['city'] = {'S': geo_data['city']}
            if geo_data.get('latitude') is not None:
                item['latitude'] = {'N': str(geo_data['latitude'])}
            if geo_data.get('longitude') is not None:
                item['longitude'] = {'N': str(geo_data['longitude'])}
            if geo_data.get('timezone'):
                item['timezone'] = {'S': geo_data['timezone']}
            if geo_data.get('isp'):
                item['isp'] = {'S': geo_data['isp']}
        
        # Store the visit record
        ddbClient.put_item(
            TableName=ddb_table_name,
            Item=item
        )
        
        logger.info(f"Successfully recorded visit: {visit_id} (#{visit_num_id})")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "success": True,
                "visitId": visit_id,
                "visitorCount": visit_num_id,
                "previousLastViewedDate": previous_last_updated,
                "message": "Visit recorded successfully"
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
            "body": json.dumps({"error": "Failed to record visitor data"}),
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