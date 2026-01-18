"""
Test Doku API with both Sandbox and Production endpoints
to determine which environment the Client ID belongs to
"""
import hashlib
import hmac
import base64
import uuid
import json
import requests
from datetime import datetime

client_id = "BRN-0280-1765767732062"
secret_key = "SK-Mb7Lbo9POYkyOCpv1vG2"

def test_doku_endpoint(base_url, env_name):
    print("\n" + "=" * 80)
    print("Testing {} Environment".format(env_name))
    print("URL: {}".format(base_url))
    print("=" * 80)
    
    request_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    target_path = "/checkout/v1/payment"
    
    body = {
        "order": {
            "amount": 10000,
            "invoice_number": "TEST-{}".format(int(datetime.utcnow().timestamp())),
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
    
    try:
        response = requests.post(
            "{}{}".format(base_url, target_path),
            headers=headers,
            data=json_body,
            timeout=10
        )
        
        print("Status Code: {}".format(response.status_code))
        
        try:
            resp_json = response.json()
            print("Response: {}".format(json.dumps(resp_json, indent=2)))
            
            if response.status_code == 400:
                error_code = resp_json.get("error", {}).get("code", "")
                if error_code == "invalid_client_id":
                    print("[RESULT] Client ID TIDAK VALID untuk {} environment".format(env_name))
                    return False
            elif response.status_code == 200:
                print("[RESULT] SUCCESS! Client ID VALID untuk {} environment".format(env_name))
                return True
            else:
                print("[RESULT] Unexpected status code")
                return None
        except:
            print("Response Text: {}".format(response.text))
            return None
            
    except Exception as e:
        print("[ERROR] {}".format(str(e)))
        return None

# Test both environments
print("=" * 80)
print("DOKU CLIENT ID ENVIRONMENT DETECTOR")
print("=" * 80)
print("Client ID: {}".format(client_id))
print("Testing which environment this Client ID belongs to...")

sandbox_result = test_doku_endpoint("https://api-sandbox.doku.com", "SANDBOX")
production_result = test_doku_endpoint("https://api.doku.com", "PRODUCTION")

print("\n" + "=" * 80)
print("FINAL DIAGNOSIS")
print("=" * 80)

if sandbox_result == True:
    print("[CONCLUSION] Client ID VALID untuk SANDBOX")
    print("Action: Gunakan https://api-sandbox.doku.com")
elif production_result == True:
    print("[CONCLUSION] Client ID VALID untuk PRODUCTION")
    print("Action: Gunakan https://api.doku.com")
    print("WARNING: Ganti DOKU_IS_PRODUCTION=true di config!")
elif sandbox_result == False and production_result == False:
    print("[CONCLUSION] Client ID TIDAK VALID di kedua environment")
    print("Possible reasons:")
    print("1. Client ID typo atau salah copy")
    print("2. Secret Key salah")
    print("3. Account belum diaktivasi")
    print("4. Client ID sudah expired/deactivated")
    print("\nAction Required:")
    print("- Login ke dashboard.doku.com atau dashboard-sandbox.doku.com")
    print("- Verify Client ID dan Secret Key")
    print("- Check account status")
else:
    print("[CONCLUSION] Test tidak conclusive (network error?)")

print("=" * 80)
