"""Test script to check email structure from TempMail"""
import json
from tempmail_client import TempMailClient

# Test email
email = "zztubzpa@clearbeam.pro"

# Login with premium credentials
client = TempMailClient(email="daidinh9875@gmail.com", password="123456hay")

# Get emails
emails = client.get_emails(email)

print("=" * 60)
print(f"Emails for: {email}")
print("=" * 60)

if isinstance(emails, list):
    for i, mail in enumerate(emails):
        print(f"\n--- Email {i+1} ---")
        print(f"Keys: {mail.keys()}")
        print(f"From: {mail.get('from', 'N/A')}")
        print(f"Subject: {mail.get('subject', 'N/A')}")
        print(f"Timestamp: {mail.get('timestamp', 'N/A')}")
        print(f"\n--- textBody ---")
        print(mail.get('textBody', 'EMPTY')[:500])
        print(f"\n--- htmlBody ---")
        html_body = mail.get('htmlBody', mail.get('body', 'EMPTY'))
        print(html_body[:1000] if html_body else 'EMPTY')
        print("\n" + "=" * 60)
else:
    print(f"Error: {emails}")
