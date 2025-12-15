"""Test TempMail Premium custom domain"""
import os
import sys

# Load env
from dotenv import load_dotenv
load_dotenv('config.env')

from tempmail_client import TempMailClient

TEMPMAIL_EMAIL = os.getenv('TEMPMAIL_EMAIL', '')
TEMPMAIL_PASSWORD = os.getenv('TEMPMAIL_PASSWORD', '')

print(f"Email: {TEMPMAIL_EMAIL}")
print(f"Password: {'*' * len(TEMPMAIL_PASSWORD)}")

if not TEMPMAIL_EMAIL or not TEMPMAIL_PASSWORD:
    print("ERROR: Missing TEMPMAIL_EMAIL or TEMPMAIL_PASSWORD")
    sys.exit(1)

# Login
client = TempMailClient(email=TEMPMAIL_EMAIL, password=TEMPMAIL_PASSWORD)
print(f"\nJWT Token: {client.jwt_token[:30] if client.jwt_token else 'None'}...")

# List all inboxes
print("\n=== MY INBOXES ===")
inboxes = client.list_my_inboxes()
print(f"Found {len(inboxes)} inboxes:")
for inbox in inboxes[:10]:  # Show first 10
    if isinstance(inbox, dict):
        print(f"  - {inbox.get('email', inbox)}")
    else:
        print(f"  - {inbox}")

# Test specific email
test_email = "atqpiadx@clearbeam.pro"
print(f"\n=== TESTING EMAIL: {test_email} ===")

# Check if owned
is_owned = client.is_email_owned(test_email)
print(f"Is owned: {is_owned}")

# Try to ensure it exists
print("\nEnsuring email exists...")
result = client.ensure_email_exists(test_email)
print(f"Result: {result}")

# Try to get emails
print("\nGetting emails...")
emails = client.get_emails(test_email)
print(f"Emails: {emails}")

# Try creating a new random email
print("\n=== CREATING RANDOM PREMIUM EMAIL ===")
new_email = client.create_premium_inbox()
print(f"New email: {new_email}")
