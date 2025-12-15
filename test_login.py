"""Test TempMail login directly"""
import requests

url = "https://api.tempmail.fish/auth/login"
data = {"email": "daidinh9875@gmail.com", "password": "123456hay"}

print("Testing login API...")
session = requests.Session()
response = session.post(url, json=data)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
print(f"Cookies: {dict(session.cookies)}")
print(f"Headers: {dict(response.headers)}")
