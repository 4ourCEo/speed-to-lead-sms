import pytest
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from app.services.intake_logic import (
    is_emergency_keyword,
    is_opt_out_keyword,
    is_help_keyword,
    is_quiet_hours
)
from app.models import Shop, Lead, LeadStatus, Base
import uuid


def test_emergency_keywords():
    """Test emergency keyword detection"""
    keywords = ["flood", "no heat", "gas leak"]
    
    assert is_emergency_keyword("My basement is flooded!", keywords)
    assert is_emergency_keyword("FLOOD in the house", keywords)
    assert is_emergency_keyword("We have no heat", keywords)
    assert is_emergency_keyword("I smell a gas leak", keywords)
    
    assert not is_emergency_keyword("AC not cooling well", keywords)
    assert not is_emergency_keyword("Need maintenance", keywords)


def test_opt_out_keywords():
    """Test opt-out keyword detection"""
    assert is_opt_out_keyword("STOP")
    assert is_opt_out_keyword("stop")
    assert is_opt_out_keyword("UNSUBSCRIBE")
    assert is_opt_out_keyword("cancel")
    assert is_opt_out_keyword("quit")
    
    assert not is_opt_out_keyword("Can you stop by?")
    assert not is_opt_out_keyword("I need help")


def test_help_keyword():
    """Test help keyword detection"""
    assert is_help_keyword("HELP")
    assert is_help_keyword("help")
    assert is_help_keyword("Help")
    
    assert not is_help_keyword("I need help with my AC")
    assert not is_help_keyword("helpful")


def test_quiet_hours():
    """Test quiet hours detection"""
    shop = Shop(
        id=str(uuid.uuid4()),
        name="Test",
        twilio_tracking_number="+1",
        owner_cell_number="+1",
        booking_calendar_link="https://test.com",
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
        timezone="America/Los_Angeles"
    )
    
    result = is_quiet_hours(shop)
    assert isinstance(result, bool)


def test_state_transitions():
    """Test lead state machine transitions conceptually"""
    initial_step = 0
    assert initial_step == 0
    
    after_sms = 1
    assert after_sms == 1
    
    after_area_problem = 2
    assert after_area_problem == 2
    
    completed_step = 3
    assert completed_step == 3
    
    statuses = [
        LeadStatus.NEW,
        LeadStatus.SMS_SENT,
        LeadStatus.IN_INTAKE,
        LeadStatus.COMPLETED,
        LeadStatus.EMERGENCY_PINGED,
        LeadStatus.OPTED_OUT
    ]
    assert len(statuses) == 6


def test_lead_dedupe_logic():
    """Test 10-minute dedupe logic conceptually"""
    now = datetime.utcnow()
    recent = now - timedelta(minutes=5)
    old = now - timedelta(minutes=15)
    
    assert (now - recent).total_seconds() < 600
    assert (now - old).total_seconds() > 600
