import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_registration():
    print("\n--- Testing Registration ---")
    data = {
        "email": "test_user_new@deline.ca",
        "password": "testpassword123",
        "full_name": "Test User",
        "beneficiary_number": "DGG-99999",
        "dob": "1995-05-15",
        "role": "student"
    }
    response = requests.post(f"{BASE_URL}/auth/register/", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 201

def test_login():
    print("\n--- Testing Login (with 'email') ---")
    data = {
        "email": "student@deline.ca",
        "password": "student123"
    }
    response = requests.post(f"{BASE_URL}/auth/login/", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    if response.status_code == 200:
        return response.json()['data']['access']
    return None

def test_me(token):
    print("\n--- Testing Authed Request (/auth/me/) ---")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/auth/me/", headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    # Note: student@deline.ca must exist in the DB (seed_final.py should have created it)
    token = test_login()
    if token:
        test_me(token)
    
    # Registration might fail if already exists, but we test the logic
    test_registration()
