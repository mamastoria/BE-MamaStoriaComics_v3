import requests
import json

print("=" * 80)
print("TESTING PURCHASE ENDPOINT WITH REAL TOKEN")
print("=" * 80)

url = "https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/purchase"
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzY4NzQxMTE4LCJ0eXBlIjoiYWNjZXNzIn0.SlUtHSJg12qew0vmAfqHZWzelina2lKIIV_vRzLhEP4"

headers = {
    "Authorization": "Bearer {}".format(token),
    "Content-Type": "application/json"
}

payload = {
    "packageId": 2,
    "payment_method": "DOKU"
}

print("\nRequest Details:")
print("URL: {}".format(url))
print("Headers: {}".format(headers))
print("Payload: {}".format(json.dumps(payload, indent=2)))

print("\n" + "=" * 80)
print("SENDING REQUEST...")
print("=" * 80)

try:
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )
    
    print("\nResponse Status: {}".format(response.status_code))
    print("\nResponse Headers:")
    for key, value in response.headers.items():
        print("  {}: {}".format(key, value))
    
    print("\nResponse Body:")
    try:
        response_json = response.json()
        print(json.dumps(response_json, indent=2))
        
        # Analysis
        print("\n" + "=" * 80)
        print("ANALYSIS")
        print("=" * 80)
        
        if response.status_code == 201 or response.status_code == 200:
            print("SUCCESS!")
            data = response_json.get("data", {})
            payment_url = data.get("payment_url", "")
            
            print("\nPayment Details:")
            print("  Invoice: {}".format(data.get("invoice_number")))
            print("  Amount: Rp {}".format(data.get("amount")))
            print("  Package: {}".format(data.get("package_name")))
            print("  Payment URL: {}".format(payment_url))
            
            if "checkout.doku.com" in payment_url:
                print("\n✓ CORRECT - Using Production Doku Checkout")
            elif "sandbox.doku.com" in payment_url:
                print("\n✗ WRONG - Still using Sandbox")
            elif "mock-payment" in payment_url:
                print("\n✗ WRONG - Using Mock Payment")
            else:
                print("\n? UNKNOWN - Unexpected payment URL format")
                
        elif response.status_code == 503:
            print("ERROR 503 - Service Unavailable")
            detail = response_json.get("detail", "")
            print("\nError Detail: {}".format(detail))
            
            if "invalid_client_id" in detail.lower():
                print("\n✗ STILL GETTING invalid_client_id ERROR")
                print("\nThis means:")
                print("1. Client ID is INVALID for Production API too")
                print("2. OR environment variables not loaded correctly")
                print("3. OR old revision still serving traffic")
                
                print("\nRECOMMENDATIONS:")
                print("- Check Cloud Run logs for 'DOKU CONFIG' message")
                print("- Verify revision number in logs")
                print("- Contact Doku support to verify credentials")
                print("- Consider enabling Mock Payment as temporary solution")
            else:
                print("\nDifferent error - check detail above")
        else:
            print("ERROR {} - {}".format(response.status_code, response_json.get("detail", "Unknown error")))
            
    except ValueError:
        print("Non-JSON response:")
        print(response.text)
        
except Exception as e:
    print("\nEXCEPTION: {}".format(str(e)))
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
