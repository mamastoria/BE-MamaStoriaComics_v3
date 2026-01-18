import requests
import json

print("=" * 80)
print("TESTING DOKU CONFIGURATION AFTER DEPLOYMENT")
print("=" * 80)

# Test 1: Health check
print("\n1. Service Health Check...")
try:
    resp = requests.get("https://nanobanana-backend-1089713441636.us-central1.run.app/", timeout=5)
    print("   Status: {} - Service is UP".format(resp.status_code))
except Exception as e:
    print("   ERROR: {}".format(str(e)))

# Test 2: Check Doku Config
print("\n2. Checking Doku Configuration...")
try:
    resp = requests.get(
        "https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/debug/doku-config",
        timeout=10
    )
    print("   Status: {}".format(resp.status_code))
    
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        print("\n   Configuration:")
        print("   - DOKU_IS_PRODUCTION: {}".format(data.get("DOKU_IS_PRODUCTION")))
        print("   - Base URL: {}".format(data.get("base_url")))
        print("   - Environment: {}".format(data.get("environment")))
        print("   - USE_MOCK_PAYMENT: {}".format(data.get("USE_MOCK_PAYMENT")))
        print("   - Client ID: {}".format(data.get("DOKU_CLIENT_ID")))
        
        # Verify configuration
        is_prod = data.get("DOKU_IS_PRODUCTION")
        base_url = data.get("base_url", "")
        
        print("\n   Analysis:")
        if is_prod and "api.doku.com" in base_url and "sandbox" not in base_url:
            print("   ✓ CORRECT - Using Production API")
        elif not is_prod and "sandbox" in base_url:
            print("   X WRONG - Still using Sandbox API")
        else:
            print("   ? UNKNOWN - Configuration mismatch")
            
    else:
        print("   ERROR: {}".format(resp.text))
        
except Exception as e:
    print("   ERROR: {}".format(str(e)))

# Test 3: Get packages (no auth needed)
print("\n3. Testing Packages Endpoint (no auth)...")
try:
    resp = requests.get(
        "https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/packages",
        timeout=10
    )
    print("   Status: {}".format(resp.status_code))
    if resp.status_code == 200:
        packages = resp.json().get("data", [])
        print("   Found {} packages".format(len(packages)))
    else:
        print("   ERROR: {}".format(resp.text[:200]))
except Exception as e:
    print("   ERROR: {}".format(str(e)))

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
To test purchase endpoint, you need:
1. Valid authentication token
2. Make POST request to /api/v1/subscriptions/purchase
3. Check if payment_url starts with https://checkout.doku.com/

If still getting 'invalid_client_id' error:
- Client ID may be invalid for both Sandbox AND Production
- Contact Doku support to verify credentials
- Consider alternative: Enable Mock Payment temporarily
""")
print("=" * 80)
