import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Shop, Lead, MessageLog, LeadStatus, MessageDirection
from app.services.twilio_service import send_sms


async def send_initial_sms_after_delay(
    db: Session,
    lead: Lead,
    shop: Shop,
    delay_seconds: int = 10
):
    """Background task: send initial SMS after a delay"""
    await asyncio.sleep(delay_seconds)
    
    body = f"{shop.name}: Sorry we missed your call. What area are you in, and what issue are you running into? Reply STOP to cancel."
    
    message_sid = send_sms(
        to=lead.caller_number,
        from_=shop.twilio_tracking_number,
        body=body
    )
    
    db.refresh(lead)
    lead.status = LeadStatus.SMS_SENT
    lead.current_step = 1
    lead.updated_at = datetime.utcnow()
    db.commit()
    
    message_log = MessageLog(
        lead_id=lead.id,
        direction=MessageDirection.OUTBOUND,
        body=body,
        twilio_message_sid=message_sid,
        created_at=datetime.utcnow()
    )
    db.add(message_log)
    db.commit()
    
    print(f"✓ Initial SMS sent to {lead.caller_number} for lead {lead.id}")
