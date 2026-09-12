import os
from typing import Optional
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from app.config import settings
from app.services.sms_sender import SmsSender


class TwilioSmsSender(SmsSender):
    """Twilio SMS sender implementation"""
    
    def __init__(self):
        self.client = self._get_twilio_client()
    
    def _get_twilio_client(self) -> Optional[Client]:
        """Get Twilio client if credentials are configured"""
        if settings.twilio_account_sid and settings.twilio_auth_token:
            return Client(settings.twilio_account_sid, settings.twilio_auth_token)
        return None
    
    def send_sms(self, to: str, from_: str, body: str) -> Optional[str]:
        """Send SMS via Twilio, return message SID or None"""
        if not self.client:
            print(f"[MOCK SMS - Twilio] To: {to}, From: {from_}, Body: {body}")
            return f"MOCK_SID_{to[-4:]}"
        
        try:
            message = self.client.messages.create(
                to=to,
                from_=from_,
                body=body
            )
            return message.sid
        except Exception as e:
            print(f"Error sending SMS via Twilio: {e}")
            return None


def get_twilio_client() -> Optional[Client]:
    """Get Twilio client if credentials are configured (legacy support)"""
    if settings.twilio_account_sid and settings.twilio_auth_token:
        return Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return None


def send_sms(to: str, from_: str, body: str) -> Optional[str]:
    """Send SMS via Twilio, return message SID or None (legacy support)"""
    sender = TwilioSmsSender()
    return sender.send_sms(to, from_, body)


def validate_twilio_request(url: str, params: dict, signature: str) -> bool:
    """Validate Twilio webhook signature"""
    if not settings.twilio_auth_token:
        return True
    
    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(url, params, signature)
