#!/usr/bin/env python3
"""Test login dengan credentials admin"""
import requests
import json

# BACKEND_URL = "https://nanobanana-backend-1089713441636.us-central1.run.app"
BACKEND_URL = "http://127.0.0.1:8002"  # Local testing

PHONE = "0811814563"
PASSWORD = "admin123"

print("🔐 Testing Login to MamaStoria Backend...")
print(f"   Backend: {BACKEND_URL}")
print(f"   Phone: {PHONE}")
print(f"   Password: {PASSWORD}\n")

try:
    # Login request
    login_data = {
        "identifier": PHONE,
        "password": PASSWORD
    }
    
    response = requests.post(
        f"{BACKEND_URL}/api/v1/auth/login",
        json=login_data,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}\n")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ LOGIN SUCCESSFUL!\n")
        print("=" * 80)
        print("RESPONSE:")
        print("=" * 80)
        print(json.dumps(data, indent=2))
        print("=" * 80)
        
        # Extract tokens
        if data.get('data'):
            access_token = data['data'].get('access_token')
            user = data['data'].get('user')
            
            if access_token:
                print(f"\n🎫 Access Token: {access_token[:50]}...")
            if user:
                print(f"👤 User: {user.get('full_name')} (ID: {user.get('id_users')})")
                print(f"📱 Phone: {user.get('phone_number')}")
                print(f"💰 Credits: {user.get('kredit')}")
                print(f"👑 Role: {user.get('role')}")
    else:
        print("❌ LOGIN FAILED!")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
