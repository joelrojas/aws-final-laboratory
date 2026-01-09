import json
import os
import boto3
import uuid
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

def lambda_handler(event, context):
    """
    Main Lambda entry point.
    Routes requests based on the HTTP method and route key.
    """
    print(f"Received event: {json.dumps(event)}")
    
    route_key = event.get('routeKey')
    http_method = event.get('requestContext', {}).get('http', {}).get('method')
    path_parameters = event.get('pathParameters', {})

    try:
        if http_method == 'POST' and event.get('rawPath') == '/files':
            return handle_upload_request(event)
        
        elif http_method == 'GET' and path_parameters.get('key'):
            object_key = path_parameters.get('key')
            return handle_download_request(object_key)
            
        else:
            return {
                "statusCode": 404,
                "body": json.dumps({"message": "Route not found"})
            }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal Server Error", "error": str(e)})
        }

def handle_upload_request(event):
    """
    Generates a pre-signed URL for uploading a file (PUT).
    Expires in 15 minutes.
    """
    body = {}
    if event.get('body'):
        try:
            body = json.loads(event.get('body'))
        except json.JSONDecodeError:
            pass
            
    # Determine the file name/key
    filename = body.get('filename')
    if not filename:
        # Generate a random key if not provided
        filename = str(uuid.uuid4())
    
    # Optional: Handle content type if provided, but typically signed URLs 
    # work best if the client sends the exact same Content-Type in the PUT.
    # We will keep it simple and generic.
    
    object_key = filename
    
    # Generate Pre-signed PUT URL
    # Expiration: 15 minutes (900 seconds)
    try:
        signed_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': object_key
            },
            ExpiresIn=900
        )
    except ClientError as e:
        print(f"Error generating upload URL: {e}")
        raise e

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "uploadUrl": signed_url,
            "objectKey": object_key,
            "expiresIn": 900
        })
    }

def handle_download_request(object_key):
    """
    Generates a pre-signed URL for downloading a file (GET).
    Returns an HTTP 307 Temporary Redirect to that URL.
    Expires in 1 hour (3600 seconds).
    """
    
    # Generate Pre-signed GET URL
    # Expiration: 1 hour (3600 seconds) per requirements
    try:
        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': object_key
            },
            ExpiresIn=3600
        )
    except ClientError as e:
        print(f"Error generating download URL: {e}")
        raise e

    # Return HTTP 307 Redirect
    # The 'Location' header tells the browser/client where to go.
    return {
        "statusCode": 307,
        "headers": {
            "Location": signed_url
        },
        "body": None 
    }
