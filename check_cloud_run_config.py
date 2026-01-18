import requests
import json

print("Checking current Doku configuration on Cloud Run...")
print("=" * 60)

try:
    response = requests.get(
        "https://nanobanana-backend-1089713441636.us-central1.run.app/api/v1/subscriptions/debug/doku-config",
        timeout=10
    )
    
    print("Status Code: {}".format(response.status_code))
    
    if response.status_code == 200:
        data = response.json()
        print("\nCurrent Configuration:")
        print(json.dumps(data, indent=2))
        
        config = data.get("data", {})
        is_production = config.get("DOKU_IS_PRODUCTION", False)
        base_url = config.get("base_url", "")
        use_mock = config.get("USE_MOCK_PAYMENT", False)
        
        print("\n" + "=" * 60)
        print("ANALYSIS:")
        print("=" * 60)
        print("DOKU_IS_PRODUCTION: {}".format(is_production))
        print("Base URL: {}".format(base_url))
        print("USE_MOCK_PAYMENT: {}".format(use_mock))
        
        if is_production and "api.doku.com" in base_url:
            print("\nStatus: CORRECT - Using Production API")
        elif not is_production and "api-sandbox.doku.com" in base_url:
            print("\nStatus: WRONG - Still using Sandbox API")
            print("Action: Deployment not yet updated, need to wait or redeploy")
        else:
            print("\nStatus: UNKNOWN configuration")
            
    else:
        print("Error: {}".format(response.text))
        
except Exception as e:
    print("Error: {}".format(str(e)))
