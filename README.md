# HVAC Speed-to-Lead SMS Intake Engine

**Python FastAPI + SQLAlchemy** powered missed-call intake system for HVAC/home-service businesses.

## Stack

- **Backend**: Python 3.12+ with FastAPI
- **Database**: SQLite (dev) / PostgreSQL (production)
- **Integrations**: Twilio Voice & SMS
- **ORM**: SQLAlchemy 2.0+
- **Testing**: pytest

## Architecture

### Call Flow

1. **Missed Call Detected**
   - Customer calls Twilio tracking number
   - Voice webhook detects unanswered/no-answer/busy
   - System creates lead (10-minute caller dedupe)
   - Queues auto-SMS (5-15s background delay)

2. **Initial SMS Sent**
   ```
   [Shop Name]: Sorry we missed your call. What area are you in, 
   and what issue are you running into? Reply STOP to cancel.
   ```

3. **Step 1: Area & Problem Collection**
   - Scans for emergency keywords (deterministic)
   - **Emergency path**: Flags lead, SMS owner immediately, asks for name
   - **Standard path**: Saves area/problem, asks for name

4. **Step 2: Name Collection**
   - Saves customer name
   - Marks lead COMPLETED
   - Sends Cal.com booking link

### Emergency Handling

Emergency keywords (configurable per shop):
- `burst`, `flood`, `flooding`, `no heat`, `no cool`, `gas`, `sparks`, `leak`

When detected:
1. Lead flagged as emergency
2. Owner SMS sent immediately: `[PRIORITY LEAD ALERT - Shop Name] Potential emergency reported from +1555... Call back immediately.`
3. Emergencies bypass quiet hours

### Quiet Hours

- Configurable per shop (default: 21:00 - 06:30)
- Non-emergency bot replies suppressed during quiet hours
- Emergency responses always send

## Project Structure

```
/workspace/
├── app/
│   ├── main.py                    # FastAPI app + routes
│   ├── config.py                  # Settings (DATABASE_URL, Twilio creds)
│   ├── database.py                # SQLAlchemy setup + session mgmt
│   ├── models/
│   │   └── __init__.py            # Schema: shops, leads, message_logs
│   ├── routers/
│   │   ├── voice_webhook.py       # POST /webhooks/twilio/voice
│   │   └── sms_webhook.py         # POST /webhooks/twilio/sms
│   └── services/
│       ├── intake_logic.py        # Keywords, quiet hours, dedupe
│       ├── twilio_service.py      # SMS send, signature validation
│       └── background_tasks.py    # Delayed initial SMS
├── scripts/
│   ├── seed_db.py                 # Create demo shop
│   └── generate_friday_audit.py   # Weekly audit CLI
├── tests/
│   └── test_intake.py             # pytest suite
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

## Database Schema

### `shops`
```sql
id UUID PK
name VARCHAR
twilio_tracking_number VARCHAR E.164 unique indexed
owner_cell_number VARCHAR E.164
booking_calendar_link TEXT
emergency_keywords JSON array (default: ["burst","flood",...])
quiet_hours_start VARCHAR (default: "21:00")
quiet_hours_end VARCHAR (default: "06:30")
timezone VARCHAR (default: "America/Los_Angeles")
is_active BOOLEAN (default: True)
```

### `leads`
```sql
id UUID PK
shop_id UUID FK
caller_number VARCHAR E.164 indexed
call_sid VARCHAR unique
status ENUM NEW|SMS_SENT|IN_INTAKE|COMPLETED|EMERGENCY_PINGED|UNRESPONSIVE|OPTED_OUT indexed
current_step INTEGER (0=Initial miss, 1=Awaiting Area&Problem, 2=Awaiting Name, 3=Finished)
customer_name VARCHAR nullable
area_neighborhood TEXT nullable
problem_description TEXT nullable
is_emergency BOOLEAN (default: False)
created_at TIMESTAMP UTC
updated_at TIMESTAMP UTC
```

### `message_logs`
```sql
id INTEGER PK auto
lead_id UUID FK indexed
direction ENUM OUTBOUND|INBOUND
body TEXT
twilio_message_sid VARCHAR nullable
created_at TIMESTAMP UTC
```

## Setup & Run

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt -r requirements-dev.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

**.env variables:**
```
DATABASE_URL=sqlite:///./hvac_intake.db
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
```

### 3. Seed Database

```bash
PYTHONPATH=/workspace python3 scripts/seed_db.py
```

Creates demo shop:
- Name: Demo HVAC Company
- Tracking: +15555550100
- Owner: +15555550199

### 4. Run Server

```bash
PYTHONPATH=/workspace python3 -m app.main
```

Server starts at: `http://0.0.0.0:8000`

Endpoints:
- `GET /` - Service info
- `GET /health` - Health check
- `POST /webhooks/twilio/voice` - Voice webhook
- `POST /webhooks/twilio/sms` - SMS webhook
- `GET /docs` - Interactive API docs

## Testing

### Run Test Suite

```bash
PYTHONPATH=/workspace python3 -m pytest tests/ -v
```

Tests cover:
- Emergency keyword detection
- STOP/opt-out keywords
- HELP keyword
- Quiet hours logic
- State transitions
- 10-minute dedupe logic

### Manual Smoke Tests

See **FINISH.md** for detailed 3-message smoke test:
1. STOP keyword
2. Emergency keyword
3. Normal intake flow

## Friday Audit CLI

Generate weekly intake reports:

```bash
PYTHONPATH=/workspace python3 scripts/generate_friday_audit.py \
  --shop-id=<UUID> \
  --start-date=2024-09-01 \
  --end-date=2024-09-07
```

**Output:**
```
============================================================
WEEKLY INTAKE AUDIT: Demo HVAC Company
============================================================
Dates: 2024-09-01 to 2024-09-07

• Unanswered Calls Ingested: 45
• Immediate SMS Sent: 45
• Intake Form / Text Completed: 32
• Estimates Booked / Links Sent: 32
• Emergency Priority Pings Sent: 3
• Unresponsive / Spam / Dead: 10
• Flagged Carrier Failures / Opt-Outs: 2
============================================================
```

## Twilio Configuration

### Voice Webhook

In [Twilio Console → Phone Numbers](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming):

1. Select your phone number
2. Under **Voice Configuration**:
   - **A CALL COMES IN**: Webhook
   - **URL**: `https://your-domain.com/webhooks/twilio/voice`
   - **HTTP Method**: POST

### SMS Webhook

Same page, under **Messaging Configuration**:

1. **A MESSAGE COMES IN**: Webhook
2. **URL**: `https://your-domain.com/webhooks/twilio/sms`
3. **HTTP Method**: POST

## Deployment

### PostgreSQL Migration

1. Update `.env`:
   ```
   DATABASE_URL=postgresql://user:pass@host:5432/dbname
   ```

2. Run migrations:
   ```bash
   PYTHONPATH=/workspace python3 -c "from app.database import engine, Base; from app.models import *; Base.metadata.create_all(bind=engine)"
   ```

3. Seed shop:
   ```bash
   PYTHONPATH=/workspace python3 scripts/seed_db.py
   ```

### Production Deployment

**Render.com / Railway / Fly.io:**

1. Set environment variables:
   - `DATABASE_URL`
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`

2. Build command:
   ```bash
   pip install -r requirements.txt
   ```

3. Start command:
   ```bash
   python3 -m app.main
   ```

4. Configure Twilio webhooks to your deployment URL

## Key Features

✅ **10-Minute Caller Dedupe**: Multiple calls from same number within 10 minutes reuse existing lead

✅ **Emergency Detection**: Deterministic keyword scan, no LLM required

✅ **Quiet Hours Enforcement**: Non-emergency bot replies suppressed outside business hours

✅ **Owner Emergency Alerts**: Immediate SMS to owner when emergency keywords detected

✅ **Three-Step Intake**: Area/Problem → Name → Calendar link

✅ **STOP/Help Compliance**: Standard opt-out and help keyword handling

✅ **Comprehensive Logging**: All messages logged to `message_logs` for audit

## What's NOT Included

Per spec, this system does **NOT** include:
- Auto-outreach campaigns
- Instantly integration
- HighLevel integration
- LLM/Grok for natural language parsing (deterministic logic only)

## Development

### Add New Shop

```python
from app.database import SessionLocal
from app.models import Shop
import uuid

db = SessionLocal()
shop = Shop(
    id=str(uuid.uuid4()),
    name="ABC Heating",
    twilio_tracking_number="+15551234567",
    owner_cell_number="+15559876543",
    booking_calendar_link="https://cal.com/abc-hvac/15min",
    emergency_keywords=["flood", "no heat", "gas"],
    is_active=True
)
db.add(shop)
db.commit()
```

### Query Leads

```python
from app.database import SessionLocal
from app.models import Lead, LeadStatus

db = SessionLocal()
leads = db.query(Lead).filter(
    Lead.status == LeadStatus.COMPLETED
).all()

for lead in leads:
    print(f"{lead.customer_name}: {lead.problem_description}")
```

## License

ISC
