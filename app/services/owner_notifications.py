"""Owner notification service for Slack and email notifications"""
import requests
from typing import Optional
from datetime import datetime
from app.config import settings


def send_owner_notification(
    caller_number: str,
    tracking_number: str,
    shop_name: str,
    timestamp: datetime,
    lead_id: str,
    call_sid: str
) -> dict:
    """
    Send owner notification via Slack and/or email for missed calls.
    
    Args:
        caller_number: Customer's phone number (E.164 format)
        tracking_number: Business tracking number that received the call
        shop_name: Name of the shop
        timestamp: When the call occurred
        lead_id: Lead UUID for tracking
        call_sid: Call SID for idempotency
        
    Returns:
        dict with 'slack_sent' and 'email_sent' boolean flags
    """
    results = {
        'slack_sent': False,
        'email_sent': False,
        'errors': []
    }
    
    formatted_time = timestamp.strftime("%Y-%m-%d %I:%M %p UTC")
    
    if settings.slack_webhook_url:
        try:
            slack_sent = send_slack_notification(
                caller_number=caller_number,
                tracking_number=tracking_number,
                shop_name=shop_name,
                formatted_time=formatted_time,
                lead_id=lead_id
            )
            results['slack_sent'] = slack_sent
        except Exception as e:
            results['errors'].append(f"Slack error: {str(e)}")
            print(f"Failed to send Slack notification: {e}")
    
    if settings.owner_notify_email and settings.resend_api_key:
        try:
            email_sent = send_email_notification(
                caller_number=caller_number,
                tracking_number=tracking_number,
                shop_name=shop_name,
                formatted_time=formatted_time,
                lead_id=lead_id
            )
            results['email_sent'] = email_sent
        except Exception as e:
            results['errors'].append(f"Email error: {str(e)}")
            print(f"Failed to send email notification: {e}")
    
    return results


def send_slack_notification(
    caller_number: str,
    tracking_number: str,
    shop_name: str,
    formatted_time: str,
    lead_id: str
) -> bool:
    """
    Send Slack notification via webhook.
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.slack_webhook_url:
        return False
    
    callback_phone = settings.owner_callback_phone or tracking_number
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📞 Missed Call Alert",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Shop:*\n{shop_name}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Time:*\n{formatted_time}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Caller:*\n{caller_number}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Tracking #:*\n{tracking_number}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🔔 Call them back:* {callback_phone}"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Lead ID: `{lead_id}`"
                }
            ]
        }
    ]
    
    fallback_text = f"Missed call from {caller_number} - Call them back at {callback_phone}"
    
    payload = {
        "text": fallback_text,
        "blocks": blocks
    }
    
    response = requests.post(
        settings.slack_webhook_url,
        json=payload,
        timeout=10
    )
    
    if response.status_code == 200:
        print(f"✓ Slack notification sent for lead {lead_id}")
        return True
    else:
        print(f"✗ Slack notification failed: {response.status_code} - {response.text}")
        return False


def send_email_notification(
    caller_number: str,
    tracking_number: str,
    shop_name: str,
    formatted_time: str,
    lead_id: str
) -> bool:
    """
    Send email notification via Resend API.
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.resend_api_key or not settings.owner_notify_email:
        return False
    
    callback_phone = settings.owner_callback_phone or tracking_number
    
    subject = f"Missed Call Alert - {shop_name}"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">📞 Missed Call Alert</h2>
        
        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 10px 0;"><strong>Shop:</strong> {shop_name}</p>
            <p style="margin: 10px 0;"><strong>Time:</strong> {formatted_time}</p>
            <p style="margin: 10px 0;"><strong>Caller:</strong> {caller_number}</p>
            <p style="margin: 10px 0;"><strong>Tracking Number:</strong> {tracking_number}</p>
        </div>
        
        <div style="background: #dbeafe; padding: 15px; border-left: 4px solid #2563eb; margin: 20px 0;">
            <p style="margin: 0; font-size: 16px;">
                <strong>🔔 Call them back:</strong> 
                <a href="tel:{callback_phone}" style="color: #2563eb; text-decoration: none;">
                    {callback_phone}
                </a>
            </p>
        </div>
        
        <p style="color: #6b7280; font-size: 12px; margin-top: 30px;">
            Lead ID: {lead_id}
        </p>
    </body>
    </html>
    """
    
    text_body = f"""
Missed Call Alert - {shop_name}

Shop: {shop_name}
Time: {formatted_time}
Caller: {caller_number}
Tracking Number: {tracking_number}

🔔 Call them back: {callback_phone}

---
Lead ID: {lead_id}
    """
    
    payload = {
        "from": f"{shop_name} <notifications@{_get_resend_domain()}>",
        "to": [settings.owner_notify_email],
        "subject": subject,
        "html": html_body,
        "text": text_body
    }
    
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        "https://api.resend.com/emails",
        json=payload,
        headers=headers,
        timeout=10
    )
    
    if response.status_code in [200, 201]:
        print(f"✓ Email notification sent for lead {lead_id}")
        return True
    else:
        print(f"✗ Email notification failed: {response.status_code} - {response.text}")
        return False


def _get_resend_domain() -> str:
    """
    Get the Resend sending domain.
    Default to 'resend.dev' for testing, or configure via RESEND_DOMAIN env var.
    """
    return getattr(settings, 'resend_domain', 'resend.dev')


def should_skip_sms() -> bool:
    """
    Check if SMS should be skipped based on environment configuration.
    
    Returns:
        True if SMS should be skipped (INTERIM_NO_SMS=true or SKIP_CALLER_SMS=true)
    """
    return settings.interim_no_sms or settings.skip_caller_sms
