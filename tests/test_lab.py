import boto3
import requests
import os
import pytest
import uuid

# Configuration
STACK_NAME = os.environ.get("STACK_NAME", "signed-url-file-gateway")
REGION = os.environ.get("AWS_REGION", "us-east-1")

@pytest.fixture(scope="module")
def api_endpoint():
    """
    Retrieves the API Gateway Endpoint URL from CloudFormation Stack Outputs.
    """
    client = boto3.client("cloudformation", region_name=REGION)
    try:
        response = client.describe_stacks(StackName=STACK_NAME)
    except Exception as e:
        pytest.fail(f"Could not describe stack '{STACK_NAME}': {e}")

    stacks = response.get("Stacks", [])
    if not stacks:
        pytest.fail(f"Stack '{STACK_NAME}' not found.")

    outputs = stacks[0].get("Outputs", [])
    api_url = None
    for output in outputs:
        if output["OutputKey"] == "ApiEndpoint":
            api_url = output["OutputValue"]
            break
    
    if not api_url:
        pytest.fail("ApiEndpoint output not found in CloudFormation stack.")
    
    return api_url

def test_upload_and_download_flow(api_endpoint):
    """
    Verifies the full end-to-end flow:
    1. POST /files to get a signed upload URL.
    2. PUT to that URL to upload a file.
    3. GET /files/{key} to get a download redirect.
    4. Follow redirect and verify file content matches.
    """
    
    # 1. Prepare Upload
    filename = f"test-file-{uuid.uuid4()}.txt"
    payload = {"filename": filename}
    params = {"filename": filename} # Sending in body usually, but let's stick to endpoint A logic
    
    upload_url_response = requests.post(f"{api_endpoint}/files", json=payload)
    assert upload_url_response.status_code == 200, f"Failed to get upload URL: {upload_url_response.text}"
    
    data = upload_url_response.json()
    assert "uploadUrl" in data
    assert "objectKey" in data
    
    upload_url = data["uploadUrl"]
    object_key = data["objectKey"]
    
    # 2. Upload File to S3
    file_content = "This is a test file content for Lab 3."
    # Using 'response.content' type upload via requests
    upload_response = requests.put(upload_url, data=file_content.encode('utf-8'))
    assert upload_response.status_code in [200, 201, 204], f"Failed to upload file to S3: {upload_response.status_code}"
    
    # 3. Request Download (Expect Redirect)
    # allow_redirects=False so we can inspect the 307 and Location header
    download_request_url = f"{api_endpoint}/files/{object_key}"
    redirect_response = requests.get(download_request_url, allow_redirects=False)
    
    assert redirect_response.status_code == 307, f"Expected 307 Redirect, got {redirect_response.status_code}"
    download_url = redirect_response.headers.get("Location")
    assert download_url, "Location header missing in redirect response"
    
    # 4. Download content from the signed URL
    final_download_response = requests.get(download_url)
    assert final_download_response.status_code == 200, "Failed to download file from signed URL"
    assert final_download_response.text == file_content, "Downloaded content does not match uploaded content"

