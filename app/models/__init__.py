import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Text, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    SMS_SENT = "SMS_SENT"
    IN_INTAKE = "IN_INTAKE"
    COMPLETED = "COMPLETED"
    EMERGENCY_PINGED = "EMERGENCY_PINGED"
    UNRESPONSIVE = "UNRESPONSIVE"
    OPTED_OUT = "OPTED_OUT"


class MessageDirection(str, enum.Enum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"


class Shop(Base):
    __tablename__ = "shops"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    twilio_tracking_number = Column(String(20), nullable=False, unique=True, index=True)
    owner_cell_number = Column(String(20), nullable=False)
    booking_calendar_link = Column(Text, nullable=False)
    emergency_keywords = Column(JSON, nullable=False, default=lambda: [
        "burst", "flood", "flooding", "no heat", "no cool", 
        "gas", "sparks", "leak"
    ])
    quiet_hours_start = Column(String(5), nullable=False, default="21:00")
    quiet_hours_end = Column(String(5), nullable=False, default="06:30")
    timezone = Column(String(50), nullable=False, default="America/Los_Angeles")
    is_active = Column(Boolean, nullable=False, default=True)
    
    leads = relationship("Lead", back_populates="shop")


class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_id = Column(String(36), ForeignKey("shops.id"), nullable=False, index=True)
    caller_number = Column(String(20), nullable=False, index=True)
    call_sid = Column(String(100), unique=True, nullable=False)
    status = Column(SQLEnum(LeadStatus), nullable=False, default=LeadStatus.NEW, index=True)
    current_step = Column(Integer, nullable=False, default=0)
    customer_name = Column(String(255), nullable=True)
    area_neighborhood = Column(Text, nullable=True)
    problem_description = Column(Text, nullable=True)
    is_emergency = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    shop = relationship("Shop", back_populates="leads")
    messages = relationship("MessageLog", back_populates="lead", cascade="all, delete-orphan")


class MessageLog(Base):
    __tablename__ = "message_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    direction = Column(SQLEnum(MessageDirection), nullable=False)
    body = Column(Text, nullable=False)
    twilio_message_sid = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    lead = relationship("Lead", back_populates="messages")
