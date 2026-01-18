import requests
import json

print("=" * 80)
print("DEBUGGING CLOUD RUN DOKU CONFIGURATION")
print("=" * 80)

# Test 1: Check if service is responding
print("\n1. Testing service health...")
try:
    resp = requests.get(
        "https://nanobanana-backend-1089713441636.us-central1.run.app/",
        timeout=5
    )
    print("   Service reachable: YES (Status: {})".format(resp.status_code))
except Exception as e:
    print("   Service reachable: NO - {}".format(str(e)))

# Test 2: Try to get debug config
print("\n2. Checking Doku configuration...")
try:
    resp = requests.get(
        "https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/debug/doku-config",
        timeout=10
    )
    print("   Status: {}".format(resp.status_code))
    if resp.status_code == 200:
        data = resp.json()
        print("   Response:")
        print(json.dumps(data, indent=4))
        
        config = data.get("data", {})
        print("\n   Analysis:")
        print("   - DOKU_IS_PRODUCTION: {}".format(config.get("DOKU_IS_PRODUCTION")))
        print("   - Base URL: {}".format(config.get("base_url")))
        print("   - USE_MOCK_PAYMENT: {}".format(config.get("USE_MOCK_PAYMENT")))
        print("   - Client ID (masked): {}".format(config.get("DOKU_CLIENT_ID")))
    else:
        print("   Error: {}".format(resp.text))
except Exception as e:
    print("   Error: {}".format(str(e)))

# Test 3: Check what Doku API is being hit
print("\n3. Attempting purchase to see which API is called...")
print("   (This will fail, but we can see the error)")

# We need a token, so this is just to show the approach
print("   Skipped - need authentication token")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)
print("""
If DOKU_IS_PRODUCTION is still FALSE or base_url is still sandbox:
1. Check Cloud Run revision number in logs
2. Verify new revision is serving traffic (not old one)
3. May need to delete old revisions to force new one

If DOKU_IS_PRODUCTION is TRUE but still getting invalid_client_id:
1. The Client ID might actually be invalid for Production too
2. Try contacting Doku support to verify credentials
3. Consider using Mock Payment temporarily

To check current revision:
https://console.cloud.google.com/run/detail/us-central1/nanobanana-backend-us/revisions?project=nanobananacomic-482111
""")
print("=" * 80)
