import hashlib
import hmac
import base64
import json
import uuid
from datetime import datetime
import requests

# CREDENTIALS TO TEST
CLIENT_ID = "BRN-0280-1765767732062"
SECRET_KEY = "SK-Mb7Lbo9POYkyOCpv1vG2"
IS_PRODUCTION = True

BASE_URL = "https://api.doku.com" if IS_PRODUCTION else "https://api-sandbox.doku.com"

def generate_digest(json_body: str) -> str:
    digest = hashlib.sha256(json_body.encode('utf-8')).digest()
    return base64.b64encode(digest).decode('utf-8')

def generate_signature(request_id: str, timestamp: str, target_path: str, digest: str) -> str:
    raw_signature = f"Client-Id:{CLIENT_ID}\nRequest-Id:{request_id}\nRequest-Timestamp:{timestamp}\nRequest-Target:{target_path}\nDigest:{digest}"
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        raw_signature.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    return f"HMACSHA256={base64.b64encode(signature).decode('utf-8')}"

def test_payment_request():
    target_path = "/checkout/v1/payment"
    request_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    body = {
        "order": {
            "amount": 15000,
            "invoice_number": f"TEST-{uuid.uuid4().hex[:6]}",
            "currency": "IDR",
            "callback_url": "https://google.com"
        },
        "payment": {
            "payment_due_date": 60
        },
        "customer": {
            "name": "Test User",
            "email": "test@example.com"
        }
    }
    
    json_body = json.dumps(body)
    digest = generate_digest(json_body)
    signature = generate_signature(request_id, timestamp, target_path, digest)
    
    headers = {
        "Content-Type": "application/json",
        "Client-Id": CLIENT_ID,
        "Request-Id": request_id,
        "Request-Timestamp": timestamp,
        "Signature": signature
    }
    
    print(f"Testing Connectivity to: {BASE_URL}{target_path}")
    print(f"Using Client ID: {CLIENT_ID}")
    
    try:
        response = requests.post(
            f"{BASE_URL}{target_path}",
            headers=headers,
            data=json_body,
            timeout=10
        )
        
        print(f"STATUS_CODE:{response.status_code}")
        if response.status_code != 200:
             print(f"RESPONSE_TEXT:{response.text}")
        else:
             print("RESPONSE_SUCCESS")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_payment_request()
