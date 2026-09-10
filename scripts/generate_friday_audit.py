#!/usr/bin/env python3
"""
Friday Audit CLI - Generate weekly intake audit report
"""
import sys
import argparse
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models import Shop, Lead, MessageLog, LeadStatus, MessageDirection


def generate_audit(shop_id: str, start_date: str, end_date: str):
    """Generate Friday audit report for a shop"""
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            print(f"Error: Shop {shop_id} not found")
            sys.exit(1)
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        leads = db.query(Lead).filter(
            Lead.shop_id == shop_id,
            Lead.created_at >= start_dt,
            Lead.created_at < end_dt
        ).all()
        
        unanswered_calls = len(leads)
        
        sms_sent = len([l for l in leads if l.status != LeadStatus.NEW])
        
        intake_completed = len([l for l in leads if l.status == LeadStatus.COMPLETED])
        
        calendar_links_sent = len([
            l for l in leads 
            if l.status == LeadStatus.COMPLETED and l.current_step >= 3
        ])
        
        emergency_pings = len([l for l in leads if l.is_emergency])
        
        unresponsive = len([
            l for l in leads 
            if l.status in [LeadStatus.UNRESPONSIVE, LeadStatus.SMS_SENT] and 
            (datetime.utcnow() - l.created_at).days > 2
        ])
        
        opted_out = len([l for l in leads if l.status == LeadStatus.OPTED_OUT])
        
        print("=" * 60)
        print(f"WEEKLY INTAKE AUDIT: {shop.name}")
        print("=" * 60)
        print(f"Dates: {start_date} to {end_date}")
        print()
        print(f"• Unanswered Calls Ingested: {unanswered_calls}")
        print(f"• Immediate SMS Sent: {sms_sent}")
        print(f"• Intake Form / Text Completed: {intake_completed}")
        print(f"• Estimates Booked / Links Sent: {calendar_links_sent}")
        print(f"• Emergency Priority Pings Sent: {emergency_pings}")
        print(f"• Unresponsive / Spam / Dead: {unresponsive}")
        print(f"• Flagged Carrier Failures / Opt-Outs: {opted_out}")
        print("=" * 60)
        
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate Friday audit report for HVAC intake"
    )
    parser.add_argument(
        "--shop-id",
        required=True,
        help="Shop UUID"
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date (YYYY-MM-DD)"
    )
    
    args = parser.parse_args()
    
    generate_audit(args.shop_id, args.start_date, args.end_date)


if __name__ == "__main__":
    main()
