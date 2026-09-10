from fastapi import APIRouter, Depends, Request, Form, BackgroundTasks
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse, Pause
from datetime import datetime
import uuid

from app.database import get_db
from app.models import Shop, Lead, LeadStatus
from app.services.intake_logic import find_recent_lead
from app.services.background_tasks import send_initial_sms_after_delay

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])


@router.post("/voice")
async def voice_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    To: str = Form(...),
    From: str = Form(...),
    CallSid: str = Form(...),
    CallStatus: str = Form(default="ringing"),
    db: Session = Depends(get_db)
):
    """
    Twilio Voice webhook - detects missed calls and triggers SMS intake
    """
    shop = db.query(Shop).filter(
        Shop.twilio_tracking_number == To,
        Shop.is_active == True
    ).first()
    
    if not shop:
        print(f"No active shop found for number {To}")
        return VoiceResponse().to_xml()
    
    print(f"Voice webhook: {CallStatus} - From: {From}, To: {To}, CallSid: {CallSid}")
    
    if CallStatus in ["no-answer", "busy", "failed", "canceled"]:
        existing_lead = find_recent_lead(db, shop.id, From, minutes=10)
        
        if not existing_lead:
            lead = Lead(
                id=str(uuid.uuid4()),
                shop_id=shop.id,
                caller_number=From,
                call_sid=CallSid,
                status=LeadStatus.NEW,
                current_step=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)
            
            print(f"✓ Created new lead {lead.id} for missed call from {From}")
            
            background_tasks.add_task(
                send_initial_sms_after_delay,
                db=db,
                lead=lead,
                shop=shop,
                delay_seconds=10
            )
        else:
            print(f"Skipping duplicate: Found recent lead {existing_lead.id} within 10 minutes")
    
    response = VoiceResponse()
    response.pause(length=2)
    return response.to_xml()
