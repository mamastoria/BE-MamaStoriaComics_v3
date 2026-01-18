import hashlib
import hmac
import base64
import uuid
import json
import requests
from datetime import datetime

# Credentials - PRODUCTION
client_id = "BRN-0280-1765767732062"
secret_key = "SK-Mb7Lbo9POYkyOCpv1vG2"
base_url = "https://api.doku.com"  # PRODUCTION!

print("=" * 80)
print("DOKU PRODUCTION API TEST")
print("=" * 80)
print("WARNING: This will hit PRODUCTION API!")
print("Client ID: {}".format(client_id))
print("Base URL: {}".format(base_url))
print("=" * 80)

# Generate request
request_id = str(uuid.uuid4())
timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
target_path = "/checkout/v1/payment"

# Minimal body
body = {
    "order": {
        "amount": 10000,
        "invoice_number": "TEST-PROD-{}".format(int(datetime.utcnow().timestamp())),
        "currency": "IDR"
    }
}

json_body = json.dumps(body, separators=(',', ':'))
digest = base64.b64encode(hashlib.sha256(json_body.encode('utf-8')).digest()).decode('utf-8')

raw_sig = "Client-Id:{}\nRequest-Id:{}\nRequest-Timestamp:{}\nRequest-Target:{}\nDigest:{}".format(
    client_id, request_id, timestamp, target_path, digest
)

signature = "HMACSHA256=" + base64.b64encode(
    hmac.new(secret_key.encode('utf-8'), raw_sig.encode('utf-8'), hashlib.sha256).digest()
).decode('utf-8')

headers = {
    "Content-Type": "application/json",
    "Client-Id": client_id,
    "Request-Id": request_id,
    "Request-Timestamp": timestamp,
    "Signature": signature
}

print("\nSending request to PRODUCTION API...")
print("URL: {}{}".format(base_url, target_path))

try:
    response = requests.post(
        "{}{}".format(base_url, target_path),
        headers=headers,
        data=json_body,
        timeout=15
    )
    
    print("\n" + "=" * 80)
    print("RESPONSE FROM DOKU PRODUCTION")
    print("=" * 80)
    print("Status Code: {}".format(response.status_code))
    
    try:
        resp_json = response.json()
        print("\nResponse Body:")
        print(json.dumps(resp_json, indent=2))
        
        if response.status_code == 200:
            print("\n" + "=" * 80)
            print("SUCCESS! DOKU PRODUCTION API WORKING!")
            print("=" * 80)
            print("Client ID is VALID for PRODUCTION environment")
            print("Payment URL would be: {}".format(resp_json.get("response", {}).get("payment", {}).get("url", "N/A")))
        elif response.status_code == 400:
            error = resp_json.get("error", {})
            print("\n" + "=" * 80)
            print("ERROR 400")
            print("=" * 80)
            print("Error Code: {}".format(error.get("code")))
            print("Error Message: {}".format(error.get("message")))
            
            if error.get("code") == "invalid_client_id":
                print("\nClient ID STILL INVALID even on Production!")
                print("This means there's another issue...")
            else:
                print("\nDifferent error - may need to adjust request body")
    except:
        print("\nResponse Text: {}".format(response.text))
    
except Exception as e:
    print("\n[ERROR] {}".format(str(e)))
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
