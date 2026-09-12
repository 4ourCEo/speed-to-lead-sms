"""
Startup helper to ensure Shop exists from environment variables.

This solves the ephemeral filesystem issue on platforms like Render free tier,
where SQLite is reset on every deploy/restart. If TWILIO_TRACKING_NUMBER is set,
this upserts a Shop with the configured values at startup.
"""
import uuid
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Shop


def upsert_shop_from_env(db: Session) -> None:
    """
    Upsert an active Shop from environment variables if TWILIO_TRACKING_NUMBER is set.
    
    This ensures production tracking numbers work immediately after deployment,
    even on ephemeral filesystems.
    
    Environment variables:
    - TWILIO_TRACKING_NUMBER (required): E.164 format (e.g. +15555550100)
    - SHOP_NAME (default: "Speed-to-Lead Demo")
    - SHOP_OWNER_CELL (default: same as TWILIO_TRACKING_NUMBER or +15555550199)
    - BOOKING_CALENDAR_LINK (default: https://cal.com/demo)
    """
    if not settings.twilio_tracking_number:
        print("ℹ️  No TWILIO_TRACKING_NUMBER set - skipping startup shop upsert")
        return
    
    tracking_number = settings.twilio_tracking_number
    shop_name = settings.shop_name
    owner_cell = settings.shop_owner_cell or tracking_number
    calendar_link = settings.booking_calendar_link
    
    existing_shop = db.query(Shop).filter(
        Shop.twilio_tracking_number == tracking_number
    ).first()
    
    if existing_shop:
        existing_shop.name = shop_name
        existing_shop.owner_cell_number = owner_cell
        existing_shop.booking_calendar_link = calendar_link
        existing_shop.is_active = True
        db.commit()
        print(f"✓ Updated shop for tracking number {tracking_number}")
        print(f"  Name: {shop_name}")
        print(f"  Owner Cell: {owner_cell}")
        print(f"  Calendar: {calendar_link}")
    else:
        new_shop = Shop(
            id=str(uuid.uuid4()),
            name=shop_name,
            twilio_tracking_number=tracking_number,
            owner_cell_number=owner_cell,
            booking_calendar_link=calendar_link,
            emergency_keywords=["burst", "flood", "flooding", "no heat", "no cool", "gas", "sparks", "leak"],
            quiet_hours_start="21:00",
            quiet_hours_end="06:30",
            timezone="America/Los_Angeles",
            is_active=True
        )
        db.add(new_shop)
        db.commit()
        db.refresh(new_shop)
        print(f"✓ Created shop: {new_shop.id}")
        print(f"  Name: {shop_name}")
        print(f"  Tracking: {tracking_number}")
        print(f"  Owner Cell: {owner_cell}")
        print(f"  Calendar: {calendar_link}")
