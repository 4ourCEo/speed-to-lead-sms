from fastapi import APIRouter, Depends, Request, Form
from sqlalchemy.orm import Session
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime

from app.database import get_db
from app.models import Shop, Lead, MessageLog, LeadStatus, MessageDirection
from app.services.intake_logic import (
    is_opt_out_keyword,
    is_help_keyword,
    is_emergency_keyword,
    is_quiet_hours
)
from app.services.sms_sender import send_sms

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])


@router.post("/sms")
async def sms_webhook(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Twilio SMS webhook - handles incoming SMS for lead intake
    """
    shop = db.query(Shop).filter(
        Shop.twilio_tracking_number == To,
        Shop.is_active == True
    ).first()
    
    if not shop:
        return MessagingResponse().to_xml()
    
    body_text = Body.strip()
    print(f"SMS from {From}: {body_text}")
    
    if is_opt_out_keyword(body_text):
        lead = db.query(Lead).filter(
            Lead.shop_id == shop.id,
            Lead.caller_number == From
        ).order_by(Lead.created_at.desc()).first()
        
        if lead:
            lead.status = LeadStatus.OPTED_OUT
            lead.updated_at = datetime.utcnow()
            db.commit()
            
            log_message(db, lead.id, MessageDirection.INBOUND, body_text, MessageSid)
        
        resp = MessagingResponse()
        resp.message("You have been unsubscribed. You will not receive further messages.")
        return resp.to_xml()
    
    if is_help_keyword(body_text):
        resp = MessagingResponse()
        resp.message(f"{shop.name} - Contact us: {shop.owner_cell_number}")
        return resp.to_xml()
    
    lead = db.query(Lead).filter(
        Lead.shop_id == shop.id,
        Lead.caller_number == From,
        Lead.status.notin_([LeadStatus.OPTED_OUT, LeadStatus.COMPLETED])
    ).order_by(Lead.created_at.desc()).first()
    
    if not lead:
        resp = MessagingResponse()
        resp.message("We don't have an active intake for your number. Please call us directly.")
        return resp.to_xml()
    
    log_message(db, lead.id, MessageDirection.INBOUND, body_text, MessageSid)
    
    response_text = ""
    
    if lead.current_step == 1:
        lead.problem_description = body_text
        
        if any(word in body_text.lower() for word in ['in', 'at', 'the', 'my', 'our']):
            words = body_text.split()
            for i, word in enumerate(words):
                if word.lower() in ['in', 'at', 'the', 'my', 'our'] and i + 1 < len(words):
                    lead.area_neighborhood = ' '.join(words[i+1:min(i+4, len(words))])
                    break
        
        is_emergency = is_emergency_keyword(body_text, shop.emergency_keywords)
        
        if is_emergency:
            lead.is_emergency = True
            lead.status = LeadStatus.EMERGENCY_PINGED
            lead.current_step = 2
            lead.updated_at = datetime.utcnow()
            db.commit()
            
            emergency_body = f"[PRIORITY LEAD ALERT - {shop.name}] Potential emergency reported from {From}: '{body_text}'. Call back immediately."
            send_sms(
                to=shop.owner_cell_number,
                from_=shop.twilio_tracking_number,
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
        lead.customer_name = body_text
        lead.current_step = 3
        lead.status = LeadStatus.COMPLETED
        lead.updated_at = datetime.utcnow()
        db.commit()
        
        response_text = f"Thanks, {body_text}! Book your appointment here: {shop.booking_calendar_link}"
    
    else:
        response_text = "Thanks! We have your information and will be in touch soon."
    
    should_send = True
    if not lead.is_emergency and is_quiet_hours(shop):
        should_send = False
        print(f"Quiet hours: Skipping outbound reply for lead {lead.id}")
    
    if should_send and response_text:
        message_sid = send_sms(
            to=From,
            from_=shop.twilio_tracking_number,
            body=response_text
        )
        log_message(db, lead.id, MessageDirection.OUTBOUND, response_text, message_sid)
    
    return MessagingResponse().to_xml()


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
