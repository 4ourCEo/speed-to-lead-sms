import requests
from typing import Optional
from app.config import settings
from app.services.sms_sender import SmsSender


class CallRailSmsSender(SmsSender):
    """CallRail SMS sender implementation using API v3"""
    
    def __init__(self):
        self.api_key = settings.callrail_api_key
        self.account_id = settings.callrail_account_id
        self.company_id = settings.callrail_company_id
        self.base_url = f"https://api.callrail.com/v3/a/{self.account_id}"
    
    def send_sms(self, to: str, from_: str, body: str) -> Optional[str]:
        """
        Send SMS via CallRail API v3
        
        Returns:
            Message ID from CallRail or None if failed
        """
        if not all([self.api_key, self.account_id, self.company_id]):
            print(f"[MOCK SMS - CallRail] To: {to}, From: {from_}, Body: {body}")
            return f"MOCK_CALLRAIL_{to[-4:]}"
        
        url = f"{self.base_url}/text-messages.json"
        
        headers = {
            "Authorization": f"Token token={self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "company_id": self.company_id,
            "customer_phone_number": to,
            "business_phone_number": from_,
            "content": body
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            message_id = data.get("id")
            print(f"✓ CallRail SMS sent successfully: {message_id}")
            return str(message_id) if message_id else None
            
        except requests.exceptions.RequestException as e:
            print(f"Error sending SMS via CallRail: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response body: {e.response.text}")
            return None
