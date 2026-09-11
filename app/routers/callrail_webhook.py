from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.database import get_db
from app.models import Shop, Lead, LeadStatus, MessageLog, MessageDirection
from app.services.intake_logic import (
    find_recent_lead,
    is_opt_out_keyword,
    is_help_keyword,
    is_emergency_keyword,
    is_quiet_hours
)
from app.services.background_tasks import send_initial_sms_after_delay
from app.services.sms_sender import send_sms

router = APIRouter(prefix="/webhooks/callrail", tags=["callrail"])


@router.post("/call")
async def callrail_call_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    CallRail post-call webhook - detects missed calls and triggers SMS intake
    
    Expected payload fields (see CallRail webhook docs):
    - tracking_phone_number: The tracking number that received the call
    - customer_phone_number: The caller's phone number
    - id: CallRail call ID
    - answered: Boolean indicating if call was answered
    - call_type: e.g., "abandoned", "missed", "answered"
    """
    try:
        body = await request.json()
    except Exception as e:
        print(f"Error parsing CallRail call webhook: {e}")
        return {"status": "error", "message": "Invalid JSON"}
    
    tracking_number = body.get("tracking_phone_number")
    customer_number = body.get("customer_phone_number")
    call_id = body.get("id")
    answered = body.get("answered", False)
    call_type = body.get("call_type", "")
    
    if not all([tracking_number, customer_number, call_id]):
        print(f"Missing required fields in CallRail call webhook")
        return {"status": "error", "message": "Missing required fields"}
    
    shop = db.query(Shop).filter(
        Shop.twilio_tracking_number == tracking_number,
        Shop.is_active == True
    ).first()
    
    if not shop:
        print(f"No active shop found for CallRail tracking number {tracking_number}")
        return {"status": "ok", "message": "No matching shop"}
    
    print(f"CallRail call webhook: Type: {call_type}, Answered: {answered}, From: {customer_number}, To: {tracking_number}, ID: {call_id}")
    
    is_missed = not answered or call_type in ["abandoned", "missed", "unanswered"]
    
    if is_missed:
        existing_lead = find_recent_lead(db, shop.id, customer_number, minutes=10)
        
        if not existing_lead:
            lead = Lead(
                id=str(uuid.uuid4()),
                shop_id=shop.id,
                caller_number=customer_number,
                call_sid=str(call_id),
                status=LeadStatus.NEW,
                current_step=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)
            
            print(f"✓ Created new lead {lead.id} for missed CallRail call from {customer_number}")
            
            background_tasks.add_task(
                send_initial_sms_after_delay,
                db=db,
                lead=lead,
                shop=shop,
                delay_seconds=10
            )
        else:
            print(f"Skipping duplicate: Found recent lead {existing_lead.id} within 10 minutes")
    
    return {"status": "ok"}


@router.post("/sms")
async def callrail_sms_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    CallRail Text Message Received webhook - handles incoming SMS for lead intake
    
    Expected payload fields (see CallRail webhook docs):
    - direction: "incoming" or "outgoing"
    - content: Message body text
    - customer_phone_number: Customer's phone number (source when incoming)
    - tracking_phone_number: Business tracking number (destination when incoming)
    - id: CallRail message ID
    """
    try:
        body = await request.json()
    except Exception as e:
        print(f"Error parsing CallRail SMS webhook: {e}")
        return {"status": "error", "message": "Invalid JSON"}
    
    direction = body.get("direction")
    content = body.get("content", "").strip()
    customer_number = body.get("customer_phone_number")
    tracking_number = body.get("tracking_phone_number")
    message_id = body.get("id")
    
    if direction != "incoming":
        return {"status": "ok", "message": "Ignoring outgoing message"}
    
    if not all([customer_number, tracking_number, content]):
        print(f"Missing required fields in CallRail SMS webhook")
        return {"status": "error", "message": "Missing required fields"}
    
    shop = db.query(Shop).filter(
        Shop.twilio_tracking_number == tracking_number,
        Shop.is_active == True
    ).first()
    
    if not shop:
        print(f"No active shop found for CallRail tracking number {tracking_number}")
        return {"status": "ok", "message": "No matching shop"}
    
    print(f"CallRail SMS from {customer_number}: {content}")
    
    if is_opt_out_keyword(content):
        lead = db.query(Lead).filter(
            Lead.shop_id == shop.id,
            Lead.caller_number == customer_number
        ).order_by(Lead.created_at.desc()).first()
        
        if lead:
            lead.status = LeadStatus.OPTED_OUT
            lead.updated_at = datetime.utcnow()
            db.commit()
            
            log_message(db, lead.id, MessageDirection.INBOUND, content, str(message_id))
        
        response_text = "You have been unsubscribed. You will not receive further messages."
        message_sid = send_sms(
            to=customer_number,
            from_=tracking_number,
            body=response_text
        )
        if lead:
            log_message(db, lead.id, MessageDirection.OUTBOUND, response_text, message_sid)
        
        return {"status": "ok"}
    
    if is_help_keyword(content):
        response_text = f"{shop.name} - Contact us: {shop.owner_cell_number}"
        send_sms(
            to=customer_number,
            from_=tracking_number,
            body=response_text
        )
        return {"status": "ok"}
    
    lead = db.query(Lead).filter(
        Lead.shop_id == shop.id,
        Lead.caller_number == customer_number,
        Lead.status.notin_([LeadStatus.OPTED_OUT, LeadStatus.COMPLETED])
    ).order_by(Lead.created_at.desc()).first()
    
    if not lead:
        response_text = "We don't have an active intake for your number. Please call us directly."
        send_sms(
            to=customer_number,
            from_=tracking_number,
            body=response_text
        )
        return {"status": "ok"}
    
    log_message(db, lead.id, MessageDirection.INBOUND, content, str(message_id))
    
    response_text = ""
    
    if lead.current_step == 1:
        lead.problem_description = content
        
        if any(word in content.lower() for word in ['in', 'at', 'the', 'my', 'our']):
            words = content.split()
            for i, word in enumerate(words):
                if word.lower() in ['in', 'at', 'the', 'my', 'our'] and i + 1 < len(words):
                    lead.area_neighborhood = ' '.join(words[i+1:min(i+4, len(words))])
                    break
        
        is_emergency = is_emergency_keyword(content, shop.emergency_keywords)
        
        if is_emergency:
            lead.is_emergency = True
            lead.status = LeadStatus.EMERGENCY_PINGED
            lead.current_step = 2
            lead.updated_at = datetime.utcnow()
            db.commit()
            
            emergency_body = f"[PRIORITY LEAD ALERT - {shop.name}] Potential emergency reported from {customer_number}: '{content}'. Call back immediately."
            send_sms(
                to=shop.owner_cell_number,
                from_=tracking_number,
                body=emergency_body
            )
            log_message(db, lead.id, MessageDirection.OUTBOUND, emergency_body, None)
            
            print(f"🚨 EMERGENCY: Sent owner alert for lead {lead.id}")
            
            response_text = "Thanks. We have flagged this as an urgent priority for our on-call tech. What is your full name?"
        else:
            lead.current_step = 2
            lead.status = LeadStatus.IN_INTAKE
            lead.updated_at = datetime.utcnow()
            db.commit()
            response_text = "Got it. What is your full name?"
    
    elif lead.current_step == 2:
        lead.customer_name = content
        lead.current_step = 3
        lead.status = LeadStatus.COMPLETED
        lead.updated_at = datetime.utcnow()
        db.commit()
        
        response_text = f"Thanks, {content}! Book your appointment here: {shop.booking_calendar_link}"
    
    else:
        response_text = "Thanks! We have your information and will be in touch soon."
    
    should_send = True
    if not lead.is_emergency and is_quiet_hours(shop):
        should_send = False
        print(f"Quiet hours: Skipping outbound reply for lead {lead.id}")
    
    if should_send and response_text:
        message_sid = send_sms(
            to=customer_number,
            from_=tracking_number,
            body=response_text
        )
        log_message(db, lead.id, MessageDirection.OUTBOUND, response_text, message_sid)
    
    return {"status": "ok"}


def log_message(db: Session, lead_id: str, direction: MessageDirection, body: str, message_sid: str = None):
    """Helper to log message to database"""
    log = MessageLog(
        lead_id=lead_id,
        direction=direction,
        body=body,
        twilio_message_sid=message_sid,
        created_at=datetime.utcnow()
    )
    db.add(log)
    db.commit()
