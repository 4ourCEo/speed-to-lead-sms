import pytest
import json
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.main import app
from app.database import Base, get_db
from app.models import Shop, Lead, LeadStatus
import uuid


TEST_DATABASE_URL = "sqlite:///./test_callrail.db"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Setup and teardown database for each test"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def shop():
    """Create and return a test shop"""
    db = TestingSessionLocal()
    
    test_shop = Shop(
        id=str(uuid.uuid4()),
        name="Test HVAC",
        twilio_tracking_number="+15555550100",
        owner_cell_number="+15555550199",
        booking_calendar_link="https://test.com/book",
        emergency_keywords=["flood", "no heat", "gas leak"],
        is_active=True
    )
    db.add(test_shop)
    db.commit()
    db.refresh(test_shop)
    db.close()
    
    return test_shop


def test_callrail_missed_call_creates_lead(shop):
    """Test that CallRail missed call webhook creates a new lead"""
    payload = {
        "tracking_phone_number": shop.twilio_tracking_number,
        "customer_phone_number": "+15555551234",
        "id": "callrail_call_123",
        "answered": False,
        "call_type": "missed"
    }
    
    response = client.post("/webhooks/callrail/call", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    time.sleep(0.5)
    
    db = TestingSessionLocal()
    lead = db.query(Lead).filter(Lead.caller_number == "+15555551234").first()
    db.close()
    
    assert lead is not None
    assert lead.status in [LeadStatus.NEW, LeadStatus.SMS_SENT]
    assert lead.call_sid == "callrail_call_123"


def test_callrail_answered_call_no_lead(shop):
    """Test that answered CallRail calls don't create leads"""
    payload = {
        "tracking_phone_number": shop.twilio_tracking_number,
        "customer_phone_number": "+15555551235",
        "id": "callrail_call_124",
        "answered": True,
        "call_type": "answered"
    }
    
    response = client.post("/webhooks/callrail/call", json=payload)
    assert response.status_code == 200
    
    db = TestingSessionLocal()
    lead = db.query(Lead).filter(Lead.caller_number == "+15555551235").first()
    db.close()
    
    assert lead is None


def test_callrail_sms_emergency_detection(shop):
    """Test that CallRail SMS webhook detects emergency keywords"""
    db = TestingSessionLocal()
    
    lead = Lead(
        id=str(uuid.uuid4()),
        shop_id=shop.id,
        caller_number="+15555551236",
        call_sid="test_call_sid",
        status=LeadStatus.SMS_SENT,
        current_step=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(lead)
    db.commit()
    lead_id = lead.id
    db.close()
    
    payload = {
        "direction": "incoming",
        "content": "My basement is flooding!",
        "customer_phone_number": "+15555551236",
        "tracking_phone_number": shop.twilio_tracking_number,
        "id": "callrail_msg_123"
    }
    
    response = client.post("/webhooks/callrail/sms", json=payload)
    assert response.status_code == 200
    
    db = TestingSessionLocal()
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    db.close()
    
    assert lead.is_emergency == True
    assert lead.status == LeadStatus.EMERGENCY_PINGED


def test_callrail_sms_opt_out(shop):
    """Test that CallRail SMS webhook handles opt-out keywords"""
    db = TestingSessionLocal()
    
    lead = Lead(
        id=str(uuid.uuid4()),
        shop_id=shop.id,
        caller_number="+15555551237",
        call_sid="test_call_sid",
        status=LeadStatus.SMS_SENT,
        current_step=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(lead)
    db.commit()
    lead_id = lead.id
    db.close()
    
    payload = {
        "direction": "incoming",
        "content": "STOP",
        "customer_phone_number": "+15555551237",
        "tracking_phone_number": shop.twilio_tracking_number,
        "id": "callrail_msg_124"
    }
    
    response = client.post("/webhooks/callrail/sms", json=payload)
    assert response.status_code == 200
    
    db = TestingSessionLocal()
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    db.close()
    
    assert lead.status == LeadStatus.OPTED_OUT


def test_callrail_sms_normal_intake_flow(shop):
    """Test complete CallRail SMS intake flow"""
    db = TestingSessionLocal()
    
    lead = Lead(
        id=str(uuid.uuid4()),
        shop_id=shop.id,
        caller_number="+15555551238",
        call_sid="test_call_sid",
        status=LeadStatus.SMS_SENT,
        current_step=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(lead)
    db.commit()
    lead_id = lead.id
    db.close()
    
    payload_step1 = {
        "direction": "incoming",
        "content": "AC not working in downtown",
        "customer_phone_number": "+15555551238",
        "tracking_phone_number": shop.twilio_tracking_number,
        "id": "callrail_msg_125"
    }
    
    response = client.post("/webhooks/callrail/sms", json=payload_step1)
    assert response.status_code == 200
    
    db = TestingSessionLocal()
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    assert lead.current_step == 2
    assert lead.status == LeadStatus.IN_INTAKE
    assert "downtown" in lead.area_neighborhood
    db.close()
    
    payload_step2 = {
        "direction": "incoming",
        "content": "John Doe",
        "customer_phone_number": "+15555551238",
        "tracking_phone_number": shop.twilio_tracking_number,
        "id": "callrail_msg_126"
    }
    
    response = client.post("/webhooks/callrail/sms", json=payload_step2)
    assert response.status_code == 200
    
    db = TestingSessionLocal()
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    assert lead.customer_name == "John Doe"
    assert lead.status == LeadStatus.COMPLETED
    db.close()


def test_callrail_sms_ignores_outgoing(shop):
    """Test that CallRail webhook ignores outgoing messages"""
    payload = {
        "direction": "outgoing",
        "content": "Hello from business",
        "customer_phone_number": "+15555551239",
        "tracking_phone_number": shop.twilio_tracking_number,
        "id": "callrail_msg_127"
    }
    
    response = client.post("/webhooks/callrail/sms", json=payload)
    assert response.status_code == 200
    assert "Ignoring outgoing" in response.json()["message"]


def test_sms_sender_abstraction():
    """Test SMS sender factory returns correct implementation"""
    from app.services.sms_sender import get_sms_sender
    from app.services.twilio_service import TwilioSmsSender
    from app.services.callrail_service import CallRailSmsSender
    from app.config import settings
    
    original_provider = settings.sms_provider
    
    settings.sms_provider = "twilio"
    sender = get_sms_sender()
    assert isinstance(sender, TwilioSmsSender)
    
    settings.sms_provider = "callrail"
    sender = get_sms_sender()
    assert isinstance(sender, CallRailSmsSender)
    
    settings.sms_provider = original_provider
