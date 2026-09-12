from abc import ABC, abstractmethod
from typing import Optional


class SmsSender(ABC):
    """Abstract base class for SMS sending providers"""
    
    @abstractmethod
    def send_sms(self, to: str, from_: str, body: str) -> Optional[str]:
        """
        Send SMS message
        
        Args:
            to: Recipient phone number (E.164 format)
            from_: Sender phone number (E.164 format)
            body: Message content
            
        Returns:
            Message ID/SID or None if failed
        """
        pass


def get_sms_sender() -> SmsSender:
    """
    Factory function to get the appropriate SMS sender based on configuration
    """
    from app.config import settings
    
    if settings.sms_provider == "callrail":
        from app.services.callrail_service import CallRailSmsSender
        return CallRailSmsSender()
    else:
        from app.services.twilio_service import TwilioSmsSender
        return TwilioSmsSender()


def send_sms(to: str, from_: str, body: str) -> Optional[str]:
    """
    Send SMS using the configured provider
    
    Args:
        to: Recipient phone number (E.164 format)
        from_: Sender phone number (E.164 format)
        body: Message content
        
    Returns:
        Message ID/SID or None if failed
    """
    sender = get_sms_sender()
    return sender.send_sms(to, from_, body)
