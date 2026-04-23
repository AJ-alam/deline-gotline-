import requests

url = "http://localhost:8000/api/auth/login/"
payloads = [
    {"username": "student@example.com", "password": "password123"},
    {"email": "student@example.com", "password": "password123"}
]

for payload in payloads:
    print(f"Testing with payload: {payload}")
    try:
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)
