
import os
import time
import requests
import json
from typing import Optional

# Config
BASE_URL = os.getenv("API_BASE_URL", "https://nanobanana-backend-1089713441636.asia-southeast2.run.app")
TEST_EMAIL = os.getenv("TEST_EMAIL", "test@example.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "password123")

class ComicGenerator:
    def __init__(self):
        self.token: Optional[str] = None
        self.headers = {}

    def check_stats_endpoint(self):
        print("Checking if /admin/comics/generation-stats exists...")
        resp = requests.get(
            f"{BASE_URL}/api/v1/admin/comics/generation-stats?hours=1&limit=1",
            timeout=10
        )
        if resp.status_code == 404:
            print("❌ Endpoint NOT FOUND. Deployment might be stuck/delayed.")
            return False
        elif resp.status_code in [401, 403]:
            print(f"✅ Endpoint Protected ({resp.status_code}) - Review deployment success.")
            return True
        else:
            print(f"✅ Endpoint Accessible ({resp.status_code})")
            return True

    def login(self) -> bool:
        print(f"Logging in as {TEST_EMAIL}...")
        try:
            resp = requests.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                timeout=10
            )
            if resp.ok:
                data = resp.json()
                self.token = data.get("data", {}).get("access_token")
                self.headers = {"Authorization": f"Bearer {self.token}"}
                print("✅ Login successful")
                return True
            else:
                print(f"❌ Login failed: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

    def create_story(self):
        print("\nCreating Story Idea...")
        payload = {
            "story_idea": "A brave young rabbit named Hoppy decides to climb the tallest mountain in the forest to see what's on the other side. Along the way, he meets a wise owl who gives him advice.",
            "style_id": 6, # Ghibli style usually
            "genre_ids": [1], # Adventure
            "page_count": 2 # Short 2 pages comic for faster test
        }
        
        resp = requests.post(f"{BASE_URL}/api/v1/comics/story", json=payload, headers=self.headers)
        if resp.ok:
            data = resp.json()
            comic_id = data.get("data", {}).get("id")
            print(f"✅ Story Created! Comic ID: {comic_id}")
            return comic_id
        else:
            print(f"❌ Create Story Failed: {resp.text}")
            return None

    def generate_comic(self, comic_id):
        print(f"\nTriggering Generation for Comic {comic_id}...")
        resp = requests.post(
            f"{BASE_URL}/api/v1/comics/{comic_id}/generate", 
            headers=self.headers,
            timeout=30 # Initial request might take a bit
        )
        if resp.ok:
            print("✅ Generation Helper Triggered!")
            return True
        else:
            print(f"❌ Generation Trigger Failed: {resp.text}")
            return False

    def monitor_progress(self, comic_id):
        print("\nMonitoring Progress...")
        start_time = time.time()
        last_status = None
        
        while True:
            try:
                # Check status
                resp = requests.get(f"{BASE_URL}/api/v1/comics/{comic_id}", headers=self.headers)
                data = resp.json().get("data", {})
                status = data.get("draft_job_status")
                
                if status != last_status:
                    print(f"[{int(time.time()-start_time)}s] Status: {status}")
                    last_status = status
                
                if status == "COMPLETED":
                    print("\n✅ Comic Generation COMPLETED!")
                    return True
                elif status in ["FAILED", "SCRIPT_FAILED"]:
                    print(f"\n❌ Comic Generation FAILED! Status: {status}")
                    return False
                
                time.sleep(3)
                
                # Timeout safety (e.g. 5 mins)
                if time.time() - start_time > 300:
                    print("TIMEOUT waiting for completion.")
                    return False
                    
            except Exception as e:
                print(f"Error checking status: {e}")
                time.sleep(3)

if __name__ == "__main__":
    generator = ComicGenerator()
    generator.check_stats_endpoint()
    
    if generator.login():
        comic_id = generator.create_story()
        if comic_id:
            # Wait a bit for async script gen (usually very fast but let's be safe)
            # Actually create_story does script gen synchronously in current code? 
            # Re-checking: create_story endpoint does script gen synchronously.
            # But generate_comic endpoint does render async.
            
            # Let's check status first to see if script is ready
            # Actually create_story calls core.make_two_part_script so it should be SCRIPT_READY immediately.
            
            if generator.generate_comic(comic_id):
                generator.monitor_progress(comic_id)
