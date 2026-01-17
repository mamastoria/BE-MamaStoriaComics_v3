"""
UAT Performance Test Script for MamaStoria
Run: python tests/uat_performance_test.py

Prerequisites:
- pip install requests tabulate
- Set TEST_EMAIL and TEST_PASSWORD environment variables
"""

import os
import time
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
import json

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "https://nanobanana-backend-1089713441636.us-central1.run.app")
TEST_EMAIL = os.getenv("TEST_EMAIL", "test@example.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "password123")

class PerformanceTest:
    def __init__(self):
        self.token: Optional[str] = None
        self.results: List[Dict[str, Any]] = []
        
    def login(self) -> bool:
        """Login and get auth token"""
        try:
            resp = requests.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                timeout=10
            )
            if resp.ok:
                data = resp.json()
                self.token = data.get("data", {}).get("access_token")
                print(f"✅ Login successful")
                return True
            else:
                print(f"❌ Login failed: {resp.status_code}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def _request(self, method: str, endpoint: str, **kwargs) -> tuple:
        """Make request and measure time"""
        url = f"{BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        start = time.time()
        try:
            resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            elapsed = (time.time() - start) * 1000  # ms
            return resp, elapsed
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return None, elapsed
    
    def test_endpoint(self, name: str, method: str, endpoint: str, 
                      expected_status: int = 200, **kwargs) -> Dict:
        """Test single endpoint"""
        resp, elapsed = self._request(method, endpoint, **kwargs)
        
        success = resp is not None and resp.status_code == expected_status
        status_code = resp.status_code if resp else 0
        
        result = {
            "name": name,
            "endpoint": endpoint,
            "method": method,
            "status": status_code,
            "time_ms": round(elapsed, 2),
            "success": success
        }
        self.results.append(result)
        
        icon = "✅" if success else "❌"
        print(f"{icon} {name}: {elapsed:.0f}ms ({status_code})")
        
        return result
    
    def run_basic_tests(self):
        """Run basic API tests"""
        print("\n" + "="*60)
        print("🧪 BASIC API TESTS")
        print("="*60 + "\n")
        
        # Public endpoints
        self.test_endpoint("Health Check", "GET", "/health")
        self.test_endpoint("List Styles", "GET", "/api/v1/styles")
        self.test_endpoint("List Genres", "GET", "/api/v1/genres")
        self.test_endpoint("List Comics", "GET", "/api/v1/comics?page=1&per_page=10")
        self.test_endpoint("List Characters", "GET", "/api/v1/characters")
        self.test_endpoint("List Backgrounds", "GET", "/api/v1/backgrounds")
        
        # Check if we need auth for protected endpoints
        if not self.token:
            if not self.login():
                print("\n⚠️ Skipping authenticated tests (login failed)")
                return
        
        # Protected endpoints
        self.test_endpoint("List Drafts", "GET", "/api/v1/comics/drafts")
        self.test_endpoint("Get Profile", "GET", "/api/v1/profile")
        self.test_endpoint("Get Notifications", "GET", "/api/v1/notifications")
    
    def run_comic_detail_tests(self, comic_ids: List[int] = None):
        """Test comic detail endpoints"""
        print("\n" + "="*60)
        print("🧪 COMIC DETAIL TESTS")
        print("="*60 + "\n")
        
        if not comic_ids:
            # Get some comic IDs from list
            resp, _ = self._request("GET", "/api/v1/comics?page=1&per_page=5")
            if resp and resp.ok:
                data = resp.json()
                comics = data.get("data", [])
                comic_ids = [c["id"] for c in comics[:3]]
        
        for comic_id in comic_ids:
            self.test_endpoint(f"Comic {comic_id} Detail", "GET", f"/api/v1/comics/{comic_id}")
            self.test_endpoint(f"Comic {comic_id} Panels", "GET", f"/api/v1/comics/{comic_id}/panels")
    
    def run_load_test(self, endpoint: str, iterations: int = 10):
        """Run load test on single endpoint"""
        print(f"\n" + "="*60)
        print(f"🧪 LOAD TEST: {endpoint} ({iterations} iterations)")
        print("="*60 + "\n")
        
        times = []
        for i in range(iterations):
            resp, elapsed = self._request("GET", endpoint)
            times.append(elapsed)
            print(f"  Iteration {i+1}: {elapsed:.0f}ms")
        
        avg = sum(times) / len(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        min_t = min(times)
        max_t = max(times)
        
        print(f"\n📊 Results:")
        print(f"  Average: {avg:.0f}ms")
        print(f"  P95: {p95:.0f}ms")
        print(f"  Min: {min_t:.0f}ms")
        print(f"  Max: {max_t:.0f}ms")
        
        return {
            "endpoint": endpoint,
            "iterations": iterations,
            "avg_ms": round(avg, 2),
            "p95_ms": round(p95, 2),
            "min_ms": round(min_t, 2),
            "max_ms": round(max_t, 2)
        }
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60 + "\n")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed
        
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {passed/total*100:.1f}%")
        
        if self.results:
            times = [r["time_ms"] for r in self.results]
            print(f"\n⏱️ Response Times:")
            print(f"  Average: {sum(times)/len(times):.0f}ms")
            print(f"  Fastest: {min(times):.0f}ms")
            print(f"  Slowest: {max(times):.0f}ms")
        
        # Show failed tests
        failed_tests = [r for r in self.results if not r["success"]]
        if failed_tests:
            print(f"\n❌ Failed Tests:")
            for t in failed_tests:
                print(f"  - {t['name']}: {t['status']} ({t['time_ms']}ms)")
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": round(passed/total*100, 2) if total > 0 else 0
        }
    
    def export_results(self, filename: str = None):
        """Export results to JSON"""
        if not filename:
            filename = f"uat_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output = {
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "summary": self.print_summary(),
            "results": self.results
        }
        
        with open(filename, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"\n📁 Results exported to: {filename}")


def main():
    print("="*60)
    print("🎬 MamaStoria UAT Performance Test")
    print(f"📍 Target: {BASE_URL}")
    print(f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    tester = PerformanceTest()
    
    # Run tests
    tester.run_basic_tests()
    tester.run_comic_detail_tests()
    tester.run_load_test("/api/v1/comics?page=1&per_page=10", iterations=5)
    
    # Summary
    tester.print_summary()
    tester.export_results()


if __name__ == "__main__":
    main()
