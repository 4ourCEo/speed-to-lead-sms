from typing import Optional
from datetime import datetime, timedelta
import pytz
from sqlalchemy.orm import Session
from app.models import Shop, Lead, LeadStatus


def is_quiet_hours(shop: Shop) -> bool:
    """Check if current time is within shop's quiet hours"""
    try:
        tz = pytz.timezone(shop.timezone)
        now = datetime.now(tz)
        current_time = now.time()
        
        start_hour, start_minute = map(int, shop.quiet_hours_start.split(':'))
        end_hour, end_minute = map(int, shop.quiet_hours_end.split(':'))
        
        start_time = datetime.now(tz).replace(hour=start_hour, minute=start_minute).time()
        end_time = datetime.now(tz).replace(hour=end_hour, minute=end_minute).time()
        
        if start_time <= end_time:
            return current_time >= start_time and current_time <= end_time
        else:
            return current_time >= start_time or current_time <= end_time
    except Exception as e:
        print(f"Error checking quiet hours: {e}")
        return False


def is_emergency_keyword(text: str, keywords: list[str]) -> bool:
    """Check if text contains any emergency keywords (case-insensitive)"""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def find_recent_lead(db: Session, shop_id: str, caller_number: str, minutes: int = 10) -> Optional[Lead]:
    """Find lead from same caller within last N minutes"""
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    return db.query(Lead).filter(
        Lead.shop_id == shop_id,
        Lead.caller_number == caller_number,
        Lead.created_at >= cutoff
    ).order_by(Lead.created_at.desc()).first()


def is_opt_out_keyword(text: str) -> bool:
    """Check if text is an opt-out keyword"""
    opt_out_keywords = ["stop", "unsubscribe", "cancel", "quit", "end"]
    text_lower = text.lower().strip()
    return any(text_lower == kw or text_lower.startswith(kw + " ") for kw in opt_out_keywords)


def is_help_keyword(text: str) -> bool:
    """Check if text is a help keyword"""
    return text.lower().strip() == "help"
