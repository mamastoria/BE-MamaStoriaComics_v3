import hashlib
import hmac
import base64
import uuid
import json
import requests
from datetime import datetime

# Credentials
client_id = "BRN-0280-1765767732062"
secret_key = "SK-Mb7Lbo9POYkyOCpv1vG2"
base_url = "https://api-sandbox.doku.com"

print("=" * 80)
print("DOKU API TEST - MINIMAL REQUEST")
print("=" * 80)

# Generate request components
request_id = str(uuid.uuid4())
timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
target_path = "/checkout/v1/payment"

# Minimal request body (only required fields)
body = {
    "order": {
        "amount": 10000,
        "invoice_number": "TEST-{}".format(int(datetime.utcnow().timestamp())),
        "currency": "IDR"
    }
}

json_body = json.dumps(body, separators=(',', ':'))  # Compact JSON
print("\nRequest Body:")
print(json_body)

# Generate Digest (SHA-256 hash of body)
digest_hash = hashlib.sha256(json_body.encode('utf-8')).digest()
digest = base64.b64encode(digest_hash).decode('utf-8')
print("\nDigest: {}".format(digest))

# Generate Signature
raw_signature = "Client-Id:{}\nRequest-Id:{}\nRequest-Timestamp:{}\nRequest-Target:{}\nDigest:{}".format(
    client_id, request_id, timestamp, target_path, digest
)

print("\nRaw Signature String:")
print(repr(raw_signature))

signature_hmac = hmac.new(
    secret_key.encode('utf-8'),
    raw_signature.encode('utf-8'),
    hashlib.sha256
).digest()
signature = "HMACSHA256=" + base64.b64encode(signature_hmac).decode('utf-8')

print("\nSignature: {}".format(signature))

# Headers
headers = {
    "Content-Type": "application/json",
    "Client-Id": client_id,
    "Request-Id": request_id,
    "Request-Timestamp": timestamp,
    "Signature": signature
}

print("\n" + "=" * 80)
print("SENDING REQUEST")
print("=" * 80)
url = "{}{}".format(base_url, target_path)
print("URL: {}".format(url))

try:
    response = requests.post(
        url,
        headers=headers,
        data=json_body,
        timeout=15
    )
    
    print("\n" + "=" * 80)
    print("RESPONSE")
    print("=" * 80)
    print("Status: {}".format(response.status_code))
    print("\nBody:")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    
    # Additional diagnostics
    if response.status_code == 400:
        print("\n" + "=" * 80)
        print("DIAGNOSTICS")
        print("=" * 80)
        resp_json = response.json()
        error = resp_json.get("error", {})
        
        print("Error Code: {}".format(error.get("code")))
        print("Error Message: {}".format(error.get("message")))
        print("Error Type: {}".format(error.get("type")))
        
        # Check if it's really invalid_client_id
        if error.get("code") == "invalid_client_id":
            print("\n[CRITICAL] Client ID is being rejected by Doku")
            print("Possible reasons:")
            print("1. Client ID tidak terdaftar di sistem Doku")
            print("2. Client ID untuk Production, tapi kita hit Sandbox")
            print("3. Client ID sudah expired atau deactivated")
            print("4. Typo di Client ID (cek lagi character by character)")
            
            print("\nAction: Coba login ke dashboard-sandbox.doku.com")
            print("        dan verify Client ID benar-benar aktif")
        
except Exception as e:
    print("\n[ERROR] {}".format(str(e)))
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
