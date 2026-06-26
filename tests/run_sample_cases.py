import json
import requests
import time
import os
import sys

API_URL = "http://localhost:8000/analyze-ticket"
HEALTH_URL = "http://localhost:8000/health"

# Resolve path to sample cases JSON based on current file location
SAMPLE_CASES_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 
    "..", 
    "Preliminary Questions and Resources", 
    "SUST_Preli_Sample_Cases.json"
))

def wait_for_api():
    print(f"Waiting for API at {HEALTH_URL}...")
    for _ in range(10):
        try:
            resp = requests.get(HEALTH_URL, timeout=2)
            if resp.status_code == 200:
                print("API is up!")
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    print("API did not start in time. Did you run 'uvicorn app.main:app'?")
    return False

def run_tests():
    if not wait_for_api():
        sys.exit(1)

    if not os.path.exists(SAMPLE_CASES_PATH):
        print(f"Could not find {SAMPLE_CASES_PATH}")
        sys.exit(1)

    with open(SAMPLE_CASES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    cases = data.get("cases", [])
    print(f"\nLoaded {len(cases)} sample cases from JSON.\n")
    
    success_count = 0
    
    for case in cases:
        print(f"Testing {case['id']}: {case['label']}")
        try:
            resp = requests.post(API_URL, json=case["input"], timeout=30)
            if resp.status_code == 200:
                print("  [SUCCESS] 200 OK - Valid Schema output")
                success_count += 1
                # You can uncomment to see the payload
                # print("  Response:", json.dumps(resp.json(), indent=2))
            else:
                print(f"  [ERROR] {resp.status_code}")
                print(f"  Details: {resp.text}")
        except requests.Timeout:
            print("  [ERROR] Request timed out!")
        except Exception as e:
            print(f"  [ERROR] Exception: {e}")
        print("-" * 50)
        
    print(f"Finished testing. Passed Schema validation for {success_count}/{len(cases)} cases.")

if __name__ == "__main__":
    run_tests()
