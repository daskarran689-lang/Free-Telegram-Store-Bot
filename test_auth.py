"""Test TempMail authentication"""
from tempmail_client import TempMailClient

# Test with premium credentials
email = "daidinh9875@gmail.com"
password = "123456hay"

print("Testing login...")
client = TempMailClient(email=email, password=password)

print(f"JWT Token: {client.jwt_token}")
print(f"Session cookies: {dict(client.session.cookies)}")

# Test get emails
test_email = "zikjzgna@clearbeam.pro"
print(f"\nGetting emails for: {test_email}")
emails = client.get_emails(test_email)
print(f"Result: {emails}")
