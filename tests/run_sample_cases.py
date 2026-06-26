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
    
    for idx, case in enumerate(cases):
        print(f"Testing {case['id']}: {case['label']}")
        payload = case["input"]
        expected = case["expected_output"]
        
        try:
            print(f"  [INPUT]: {json.dumps(payload, indent=2)}")
            resp = requests.post(API_URL, json=payload, timeout=30)
            if resp.status_code == 200:
                result = resp.json()
                print(f"  [OUTPUT]: {json.dumps(result, indent=2)}")
                
                # Diff core fields
                diffs = []
                for field in ["relevant_transaction_id", "evidence_verdict", "case_type", "department", "human_review_required"]:
                    res_val = result.get(field)
                    exp_val = expected.get(field)
                    if res_val != exp_val:
                        diffs.append(f"{field}: expected {exp_val}, got {res_val}")
                        
                if diffs:
                    print("  [FAILED] Mismatches found:")
                    for d in diffs:
                        print(f"    - {d}")
                else:
                    print("  [SUCCESS] 200 OK - Core fields matched successfully.")
                    success_count += 1
            else:
                print(f"  [ERROR] {resp.status_code}")
                print(f"  Details: {resp.text}")
        except requests.Timeout:
            print("  [ERROR] Request timed out!")
        except Exception as e:
            print(f"  [ERROR] Exception: {e}")
        print("-" * 50)
        
        # Avoid Gemini Free Tier rate limit (5 requests per minute for 2.5-flash)
        if idx < len(cases) - 1:
            print("  Sleeping for 20s to respect rate limits...")
            time.sleep(20)
        
    print(f"Finished testing. Passed Schema & Core validation for {success_count}/{len(cases)} cases.")
    
    if success_count < len(cases):
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
