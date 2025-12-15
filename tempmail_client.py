"""
TempMail.fish API Client
A Python client for interacting with the tempmail.fish API
"""
import requests
import json
import re
import html
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

# Global cache for JWT token
_jwt_cache_file = "tempmail_jwt_cache.json"


class TempMailClient:
    """Client for interacting with tempmail.fish API"""
    
    BASE_URL = "https://api.tempmail.fish"
    
    def __init__(self, auth_key: Optional[str] = None, jwt_token: Optional[str] = None, email: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the TempMail client
        
        Args:
            auth_key: Authentication key for anonymous inboxes
            jwt_token: JWT token for premium accounts
            email: Premium account email (for auto-login)
            password: Premium account password (for auto-login)
        """
        self.auth_key = auth_key
        self.jwt_token = jwt_token
        self.premium_email = email
        self.premium_password = password
        self.session = requests.Session()
        
        # Try to load cached JWT first
        if email and password and not jwt_token:
            cached_jwt = self._load_cached_jwt(email)
            if cached_jwt:
                self.jwt_token = cached_jwt
                self.session.cookies.set("access_token", cached_jwt)
            else:
                self.login(email, password)
    
    def _load_cached_jwt(self, email: str) -> Optional[str]:
        """Load cached JWT token from file (skip cache, always login fresh)"""
        # JWT expires quickly (15 min), so always login fresh for reliability
        return None
    
    def _save_jwt_cache(self, email: str, jwt: str):
        """Save JWT token to cache file"""
        try:
            cache = {}
            if os.path.exists(_jwt_cache_file):
                with open(_jwt_cache_file, 'r') as f:
                    cache = json.load(f)
            cache[email] = jwt
            with open(_jwt_cache_file, 'w') as f:
                json.dump(cache, f)
        except:
            pass
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Login to premium account and get JWT token
        
        Args:
            email: Premium account email
            password: Premium account password
            
        Returns:
            dict: Login response
        """
        url = f"{self.BASE_URL}/auth/login"
        try:
            response = self.session.post(url, json={"email": email, "password": password})
            response.raise_for_status()
            data = response.json()
            
            # JWT is set in cookies automatically by session
            if "access_token" in self.session.cookies:
                self.jwt_token = self.session.cookies.get("access_token")
                # Cache the JWT token
                self._save_jwt_cache(email, self.jwt_token)
            
            return data
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        headers = {"Content-Type": "application/json"}
        
        if self.auth_key:
            headers["Authorization"] = self.auth_key
            
        return headers
    
    def create_inbox(self) -> Dict[str, Any]:
        """
        Create a new disposable inbox (anonymous)
        
        Returns:
            dict: Response containing email, authKey, and emails list
        """
        url = f"{self.BASE_URL}/emails/new-email"
        headers = {"Content-Type": "application/json"}
        
        try:
            response = self.session.post(url, headers=headers, json={})
            response.raise_for_status()
            data = response.json()
            
            # Store auth key for future requests
            if "authKey" in data:
                self.auth_key = data["authKey"]
                
            return data
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def get_emails(self, email_address: str, retry: bool = True) -> List[Dict[str, Any]]:
        """
        Retrieve messages for an inbox.
        For Premium accounts, automatically creates the custom alias first.
        
        Args:
            email_address: The inbox email address
            retry: Whether to retry with fresh login on 401
            
        Returns:
            list: List of email messages
        """
        # For Premium with JWT, always create custom alias first (fast, idempotent)
        if self.jwt_token and '@' in email_address:
            alias, domain = email_address.split('@', 1)
            self.create_custom_alias(alias, domain)  # Ignore result, may already exist
        
        url = f"{self.BASE_URL}/emails/emails"
        params = {"emailAddress": email_address}
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None:
                # Handle 401 Unauthorized - token expired, try to re-login
                if e.response.status_code == 401 and retry and self.premium_email and self.premium_password:
                    # Clear cached token and re-login
                    self._clear_jwt_cache(self.premium_email)
                    self.jwt_token = None
                    self.session.cookies.clear()
                    login_result = self.login(self.premium_email, self.premium_password)
                    if "error" not in login_result:
                        # Retry the request
                        return self.get_emails(email_address, retry=False)
                    return [{"error": f"Re-login failed: {login_result.get('error', 'Unknown error')}"}]
                elif e.response.status_code == 404:
                    return [{"error": "404 Not Found - Email không tồn tại hoặc đã hết hạn"}]
            return [{"error": str(e)}]
        except requests.exceptions.RequestException as e:
            return [{"error": str(e)}]
    
    def _clear_jwt_cache(self, email: str):
        """Clear cached JWT token for an email"""
        try:
            if os.path.exists(_jwt_cache_file):
                with open(_jwt_cache_file, 'r') as f:
                    cache = json.load(f)
                if email in cache:
                    del cache[email]
                    with open(_jwt_cache_file, 'w') as f:
                        json.dump(cache, f)
        except:
            pass
    
    def delete_inbox(self, email_address: str) -> Dict[str, Any]:
        """
        Delete an inbox and its messages
        
        Args:
            email_address: The inbox email address to delete
            
        Returns:
            dict: Response from the API
        """
        url = f"{self.BASE_URL}/emails/email"
        params = {"emailAddress": email_address}
        headers = self._get_headers()
        
        try:
            response = self.session.delete(url, params=params, headers=headers)
            response.raise_for_status()
            
            # Clear auth key after deletion
            self.auth_key = None
            
            return {"success": True, "message": "Inbox deleted successfully"}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def create_premium_inbox(self) -> Dict[str, Any]:
        """
        Create a premium inbox (requires JWT authentication)
        
        Returns:
            dict: Response containing the new inbox details
        """
        url = f"{self.BASE_URL}/emails/my-emails/random"
        headers = self._get_headers()
        
        try:
            response = self.session.post(url, headers=headers, json={})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def create_custom_alias(self, alias: str, domain: str) -> Dict[str, Any]:
        """
        Create a custom alias (requires JWT authentication and premium)
        
        Args:
            alias: The desired alias name
            domain: The domain for the alias
            
        Returns:
            dict: Response from the API
        """
        url = f"{self.BASE_URL}/emails/custom"
        headers = self._get_headers()
        payload = {"alias": alias, "domain": domain}
        
        try:
            response = self.session.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def check_alias_availability(self, alias: str, domain: str) -> Dict[str, Any]:
        """
        Check if a custom alias is available
        
        Args:
            alias: The alias to check
            domain: The domain to check
            
        Returns:
            dict: Availability status
        """
        url = f"{self.BASE_URL}/emails/custom/availability"
        params = {"alias": alias, "domain": domain}
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def list_my_inboxes(self) -> List[Dict[str, Any]]:
        """
        List all inboxes owned by authenticated user (requires JWT)
        
        Returns:
            list: List of owned inboxes
        """
        url = f"{self.BASE_URL}/emails/my-emails"
        headers = self._get_headers()
        
        try:
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return [{"error": str(e)}]
    
    def is_email_owned(self, email_address: str) -> bool:
        """
        Check if an email address is owned by the authenticated user
        
        Args:
            email_address: The email address to check
            
        Returns:
            bool: True if owned, False otherwise
        """
        inboxes = self.list_my_inboxes()
        if isinstance(inboxes, list):
            for inbox in inboxes:
                if isinstance(inbox, dict) and inbox.get('email') == email_address:
                    return True
        return False
    
    def ensure_email_exists(self, email_address: str) -> Dict[str, Any]:
        """
        Ensure an email exists in the Premium account (create if not exists)
        
        Args:
            email_address: The email address to ensure exists
            
        Returns:
            dict: Result with 'success' or 'error'
        """
        if not self.jwt_token:
            return {"error": "Premium login required"}
        
        # Check if already owned
        if self.is_email_owned(email_address):
            return {"success": True, "message": "Email already exists"}
        
        # Try to create it
        if '@' in email_address:
            alias, domain = email_address.split('@', 1)
            result = self.create_custom_alias(alias, domain)
            if "error" not in result:
                return {"success": True, "message": "Email created"}
            return result
        
        return {"error": "Invalid email format"}
    
    @staticmethod
    def clean_html(text: str) -> str:
        """
        Remove HTML tags and clean up text content
        
        Args:
            text: HTML text to clean
            
        Returns:
            str: Cleaned plain text
        """
        if not text:
            return "No content"
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Remove script and style tags with their content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        # Replace common block elements with newlines
        text = re.sub(r'</?(div|p|br|tr|table|tbody|thead)[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</h[1-6]>', '\n\n', text, flags=re.IGNORECASE)
        
        # Remove all remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple blank lines to double
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single
        text = re.sub(r'^\s+', '', text, flags=re.MULTILINE)  # Leading spaces
        
        # Remove invisible characters and zero-width spaces
        text = re.sub(r'[\u200B-\u200D\uFEFF\u00AD]', '', text)
        text = re.sub(r'[͏­\xa0]+', ' ', text)
        
        # Trim and clean up
        text = text.strip()
        
        # Limit consecutive blank lines
        lines = [line for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        return text if text else "No content"
    
    @staticmethod
    def format_email(email: Dict[str, Any]) -> str:
        """
        Format an email message for display
        
        Args:
            email: Email message dictionary
            
        Returns:
            str: Formatted email string
        """
        if "error" in email:
            return f"Error: {email['error']}"
        
        timestamp = email.get("timestamp", 0)
        dt = datetime.fromtimestamp(timestamp / 1000) if timestamp else "Unknown"
        
        # Get and clean the text body
        text_body = email.get('textBody', '')
        cleaned_body = TempMailClient.clean_html(text_body)
        
        # Limit body length for display
        max_length = 1000
        if len(cleaned_body) > max_length:
            cleaned_body = cleaned_body[:max_length] + "\n\n[... Nội dung quá dài, đã cắt bớt ...]\n"
        
        formatted = f"""
{'='*60}
From: {email.get('from', 'Unknown')}
To: {email.get('to', 'Unknown')}
Subject: {email.get('subject', 'No Subject')}
Date: {dt}
Attachments: {len(email.get('attachments', []))}
{'='*60}

{cleaned_body}

{'='*60}
"""
        return formatted
