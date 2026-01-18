import hashlib
import hmac
import base64
import uuid
import json
import requests
from datetime import datetime

# Credentials from .env
client_id = "BRN-0280-1765767732062"
secret_key = "SK-Mb7Lbo9POYkyOCpv1vG2"
base_url = "https://api-sandbox.doku.com"

# Generate request
request_id = str(uuid.uuid4())
timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
target_path = "/checkout/v1/payment"

# Request body
body = {
    "order": {
        "amount": 16500,
        "invoice_number": f"TEST-{uuid.uuid4().hex[:8]}",
        "currency": "IDR",
        "callback_url": "https://test.com/callback",
        "line_items": [
            {
                "name": "Test Package",
                "price": 16500,
                "quantity": 1
            }
        ]
    },
    "payment": {
        "payment_due_date": 60
    },
    "customer": {
        "id": "1",
        "name": "Test Customer",
        "email": "test@test.com"
    }
}

json_body = json.dumps(body)

# Generate digest
digest = base64.b64encode(hashlib.sha256(json_body.encode('utf-8')).digest()).decode('utf-8')

# Generate signature
raw_signature = f"Client-Id:{client_id}\nRequest-Id:{request_id}\nRequest-Timestamp:{timestamp}\nRequest-Target:{target_path}\nDigest:{digest}"
signature = "HMACSHA256=" + base64.b64encode(
    hmac.new(secret_key.encode('utf-8'), raw_signature.encode('utf-8'), hashlib.sha256).digest()
).decode('utf-8')

# Headers
headers = {
    "Content-Type": "application/json",
    "Client-Id": client_id,
    "Request-Id": request_id,
    "Request-Timestamp": timestamp,
    "Signature": signature
}

output = []
output.append("=" * 80)
output.append("TESTING DOKU CREDENTIALS")
output.append("=" * 80)
output.append(f"Client-Id: {client_id}")
output.append(f"Secret-Key: {secret_key[:10]}...")
output.append(f"Base URL: {base_url}")
output.append(f"Request-Id: {request_id}")
output.append(f"Timestamp: {timestamp}")
output.append(f"Target Path: {target_path}")
output.append("=" * 80)
output.append("\nSending request to Doku API...")

try:
    response = requests.post(
        f"{base_url}{target_path}",
        headers=headers,
        data=json_body,
        timeout=10
    )
    
    output.append(f"\nStatus Code: {response.status_code}")
    output.append(f"Response Headers: {dict(response.headers)}")
    output.append(f"\nResponse Body:")
    try:
        response_json = response.json()
        output.append(json.dumps(response_json, indent=2))
    except:
        output.append(response.text)
    
    if response.status_code == 200:
        output.append("\n✅ SUCCESS! Credentials are valid!")
    else:
        output.append("\n❌ ERROR! Check the response above for details.")
        
except Exception as e:
    output.append(f"\n❌ EXCEPTION: {str(e)}")
    import traceback
    output.append(traceback.format_exc())

# Write to file
with open("doku_test_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("\n".join(output))
print("\n\nResult saved to doku_test_result.txt")
