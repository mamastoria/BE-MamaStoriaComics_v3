import hashlib
import hmac
import base64
import uuid
import json
import requests
from datetime import datetime
import sys

# Set UTF-8 encoding for output
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Credentials
client_id = "BRN-0280-1765767732062"
secret_key = "SK-Mb7Lbo9POYkyOCpv1vG2"
base_url = "https://api-sandbox.doku.com"

print("=" * 80)
print("DOKU API DETAILED TEST")
print("=" * 80)
print("Client ID: {}".format(client_id))
print("Secret Key: {}".format(secret_key))
print("Base URL: {}".format(base_url))
print("=" * 80)

# Generate request components
request_id = str(uuid.uuid4())
timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
target_path = "/checkout/v1/payment"

print("\nRequest ID: {}".format(request_id))
print("Timestamp: {}".format(timestamp))
print("Target Path: {}".format(target_path))

# Request body
body = {
    "order": {
        "amount": 16500,
        "invoice_number": "TEST-{}".format(uuid.uuid4().hex[:8]),
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
print("\nRequest Body Length: {} bytes".format(len(json_body)))

# Step 1: Generate Digest
print("\n" + "=" * 80)
print("STEP 1: DIGEST CALCULATION")
print("=" * 80)
digest_bytes = hashlib.sha256(json_body.encode('utf-8')).digest()
digest = base64.b64encode(digest_bytes).decode('utf-8')
print("Digest (Base64): {}".format(digest))

# Step 2: Generate Signature
print("\n" + "=" * 80)
print("STEP 2: SIGNATURE CALCULATION")
print("=" * 80)
raw_signature = "Client-Id:{}\nRequest-Id:{}\nRequest-Timestamp:{}\nRequest-Target:{}\nDigest:{}".format(
    client_id, request_id, timestamp, target_path, digest
)
print("Raw Signature String:")
print("-" * 40)
print(raw_signature)
print("-" * 40)

signature_bytes = hmac.new(
    secret_key.encode('utf-8'),
    raw_signature.encode('utf-8'),
    hashlib.sha256
).digest()
signature = "HMACSHA256=" + base64.b64encode(signature_bytes).decode('utf-8')
print("\nSignature: {}".format(signature))

# Step 3: Prepare Headers
print("\n" + "=" * 80)
print("STEP 3: REQUEST HEADERS")
print("=" * 80)
headers = {
    "Content-Type": "application/json",
    "Client-Id": client_id,
    "Request-Id": request_id,
    "Request-Timestamp": timestamp,
    "Signature": signature
}
for key, value in headers.items():
    print("{}: {}".format(key, value))

# Step 4: Send Request
print("\n" + "=" * 80)
print("STEP 4: SENDING REQUEST TO DOKU")
print("=" * 80)
url = "{}{}".format(base_url, target_path)
print("URL: {}".format(url))

try:
    response = requests.post(
        url,
        headers=headers,
        data=json_body,
        timeout=10
    )
    
    print("\n{}".format("=" * 80))
    print("RESPONSE FROM DOKU")
    print("=" * 80)
    print("Status Code: {}".format(response.status_code))
    print("\nResponse Headers:")
    for key, value in response.headers.items():
        print("  {}: {}".format(key, value))
    
    print("\nResponse Body:")
    try:
        response_json = response.json()
        print(json.dumps(response_json, indent=2))
    except:
        print(response.text)
    
    print("\n" + "=" * 80)
    if response.status_code == 200:
        print("[SUCCESS] Request accepted by Doku")
    elif response.status_code == 400:
        print("[ERROR 400] BAD REQUEST")
        try:
            response_json = response.json()
            error_code = response_json.get("error", {}).get("code", "")
            error_msg = response_json.get("error", {}).get("message", "")
            
            print("\nError Code: {}".format(error_code))
            print("Error Message: {}".format(error_msg))
            
            if error_code == "invalid_client_id":
                print("\nDIAGNOSIS: Invalid Client ID")
                print("  - Pastikan Client ID benar dari dashboard Doku")
                print("  - Cek apakah untuk Sandbox atau Production")
                print("  - Coba copy-paste ulang dari dashboard")
            elif error_code == "invalid_signature":
                print("\nDIAGNOSIS: Invalid Signature")
                print("  - Secret Key mungkin salah")
                print("  - Cek format signature calculation")
            else:
                print("\nDIAGNOSIS: Error code = {}".format(error_code))
        except:
            pass
    elif response.status_code == 401:
        print("[ERROR 401] UNAUTHORIZED")
        print("  - Secret Key kemungkinan salah")
    else:
        print("[ERROR] HTTP {}".format(response.status_code))
    print("=" * 80)
        
except Exception as e:
    print("\n[EXCEPTION] {}".format(str(e)))
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TROUBLESHOOTING CHECKLIST")
print("=" * 80)
print("1. [OK] Client ID benar (sudah dikonfirmasi)")
print("2. [?] Secret Key - TOLONG CEK LAGI DI DASHBOARD DOKU")
print("3. [?] Environment - Pastikan Sandbox credentials untuk Sandbox API")
print("4. [?] Status Account - Pastikan account Doku aktif")
print("=" * 80)

# Save to file
with open("doku_test_output.txt", "w", encoding="utf-8") as f:
    f.write("Test completed. Check console output above.\n")
