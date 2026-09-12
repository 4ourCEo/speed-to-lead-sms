import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Shop, Lead, MessageLog, LeadStatus, MessageDirection
from app.services.sms_sender import send_sms
from app.services.owner_notifications import send_owner_notification, should_skip_sms
from app.database import SessionLocal


async def send_initial_sms_after_delay(
    db: Session,
    lead: Lead,
    shop: Shop,
    delay_seconds: int = 10
):
    """
    Background task: send initial SMS after a delay OR send owner notification.
    
    If SMS is disabled (INTERIM_NO_SMS=true) or SMS fails, send owner notification instead.
    Always create the lead and ensure owner is notified.
    """
    await asyncio.sleep(delay_seconds)
    
    lead_id = lead.id
    shop_id = shop.id
    shop_name = shop.name
    shop_tracking_number = shop.twilio_tracking_number
    
    new_db = SessionLocal()
    try:
        lead = new_db.query(Lead).filter(Lead.id == lead_id).first()
        shop = new_db.query(Shop).filter(Shop.id == shop_id).first()
        
        if not lead or not shop:
            print(f"✗ Lead or shop not found for background task")
            return
        
        sms_success = False
        skip_sms = should_skip_sms()
        
        if not skip_sms:
            body = f"{shop_name}: Sorry we missed your call. What area are you in, and what issue are you running into? Reply STOP to cancel."
            
            try:
                message_sid = send_sms(
                    to=lead.caller_number,
                    from_=shop_tracking_number,
                    body=body
                )
                
                if message_sid:
                    sms_success = True
                    lead.status = LeadStatus.SMS_SENT
                    lead.current_step = 1
                    lead.updated_at = datetime.utcnow()
                    new_db.commit()
                    
                    message_log = MessageLog(
                        lead_id=lead.id,
                        direction=MessageDirection.OUTBOUND,
                        body=body,
                        twilio_message_sid=message_sid,
                        created_at=datetime.utcnow()
                    )
                    new_db.add(message_log)
                    new_db.commit()
                    
                    print(f"✓ Initial SMS sent to {lead.caller_number} for lead {lead.id}")
                else:
                    print(f"✗ SMS send returned None for lead {lead.id}, will notify owner")
            except Exception as e:
                print(f"✗ SMS send failed for lead {lead.id}: {e}, will notify owner")
        else:
            print(f"SMS disabled via env config for lead {lead.id}, will notify owner instead")
        
        if not sms_success or skip_sms:
            if not lead.owner_notified:
                try:
                    notification_results = send_owner_notification(
                        caller_number=lead.caller_number,
                        tracking_number=shop_tracking_number,
                        shop_name=shop_name,
                        timestamp=lead.created_at,
                        lead_id=lead.id,
                        call_sid=lead.call_sid
                    )
                    
                    lead.owner_notified = True
                    lead.updated_at = datetime.utcnow()
                    new_db.commit()
                    
                    if notification_results.get('slack_sent') or notification_results.get('email_sent'):
                        print(f"✓ Owner notification sent for lead {lead.id} (Slack: {notification_results.get('slack_sent')}, Email: {notification_results.get('email_sent')})")
                    else:
                        print(f"⚠ Owner notification attempted but no channels configured for lead {lead.id}")
                        
                except Exception as e:
                    print(f"✗ Owner notification failed for lead {lead.id}: {e}")
            else:
                print(f"Owner already notified for lead {lead.id}, skipping duplicate notification")
    finally:
        new_db.close()


