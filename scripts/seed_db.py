#!/usr/bin/env python3
"""
Seed database with demo shop for local testing
"""
import uuid
from app.database import SessionLocal, engine, Base
from app.models import Shop

Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    existing = db.query(Shop).filter(Shop.name == "Demo HVAC Company").first()
    if existing:
        print(f"Demo shop already exists: {existing.id}")
    else:
        shop = Shop(
            id=str(uuid.uuid4()),
            name="Demo HVAC Company",
            twilio_tracking_number="+15555550100",
            owner_cell_number="+15555550199",
            booking_calendar_link="https://cal.com/demo-hvac/15min",
            emergency_keywords=["burst", "flood", "flooding", "no heat", "no cool", "gas", "sparks", "leak"],
            quiet_hours_start="21:00",
            quiet_hours_end="06:30",
            timezone="America/Los_Angeles",
            is_active=True
        )
        db.add(shop)
        db.commit()
        db.refresh(shop)
        print(f"✓ Created demo shop: {shop.id}")
        print(f"  Name: {shop.name}")
        print(f"  Tracking Number: {shop.twilio_tracking_number}")
        print(f"  Owner Cell: {shop.owner_cell_number}")
        print(f"  Calendar: {shop.booking_calendar_link}")

finally:
    db.close()
