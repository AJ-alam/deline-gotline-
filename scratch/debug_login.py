import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_login(email, password):
    print(f"\nTesting login for {email}...")
    try:
        login_resp = requests.post(f"{BASE_URL}/auth/login/", json={
            "email": email,
            "password": password
        })
        print(f"Login Status: {login_resp.status_code}")
        if login_resp.status_code != 200:
            print(f"Error: {login_resp.text}")
            return
        
        data = login_resp.json()
        token = data['data']['access']
        print("Login Success. Fetching /me...")
        
        me_resp = requests.get(f"{BASE_URL}/auth/me/", headers={
            "Authorization": f"Bearer {token}"
        })
        print(f"Me Status: {me_resp.status_code}")
        if me_resp.status_code != 200:
            print(f"Me Error: {me_resp.text}")
        else:
            print("Me Data retrieved successfully")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    # Test Staff (Admin)
    test_login("admin@example.com", "password123")
    # Test Director
    test_login("director@deline.ca", "director123")
