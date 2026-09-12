# Speed-to-Lead SMS Intake Engine

**Automated missed-call SMS intake system for HVAC and home service businesses.**

When customers call outside business hours, this system detects the missed call and automatically sends an SMS to collect their issue, location, and contact info—converting missed calls into booked appointments.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![Twilio](https://img.shields.io/badge/Twilio-Webhooks-orange.svg)](https://www.twilio.com/)
[![License](https://img.shields.io/badge/License-ISC-lightgrey.svg)](LICENSE)

## Demo

No public API deployment yet. Test locally via:
- Interactive API docs at `http://localhost:8000/docs`
- Health check at `http://localhost:8000/health`
- Unit tests: `pytest tests/ -v`

## How It Works

```
Customer calls → Missed → SMS sent automatically → Customer replies
                                ↓
                    "What area + what issue?"
                                ↓
                    Emergency detected? → Alert owner
                                ↓
                        "What's your name?"
                                ↓
                    Send Cal.com booking link
```

### Call Flow Details

1. **Missed Call Detected** – Twilio/CallRail voice webhook triggers on no-answer/busy
2. **Auto-SMS Sent** (5-15s delay) – "Sorry we missed your call. What area and issue?"
3. **Step 1: Area & Problem** – Customer replies, system scans for emergency keywords
4. **Step 2: Name** – System asks for customer name
5. **Step 3: Booking Link** – Sends Cal.com or similar calendar URL

**Emergency Handling**: Keywords like `flood`, `no heat`, `gas leak` trigger immediate owner SMS and bypass quiet hours.

**Quiet Hours**: Non-emergency bot replies suppressed during configured hours (default 21:00 - 06:30).

## Tech Stack

- **Backend**: Python 3.12+ with FastAPI
- **Database**: SQLite (dev) / PostgreSQL (production)
- **Integrations**: Twilio Voice & SMS, CallRail Voice & SMS
- **ORM**: SQLAlchemy 2.0+
- **Testing**: pytest with FastAPI TestClient
- **Deployment**: Render.com (see `render.yaml`)

## Architecture

```
┌──────────────┐           ┌───────────────────────┐
│   Customer   │──Call────▶│  Twilio / CallRail    │
│   Phone      │           │  Tracking Number      │
└──────────────┘           └───────────┬───────────┘
                                       │ Missed Call
                                       ▼
                              ┌────────────────┐
                              │  Voice Webhook │
                              │  (FastAPI)     │
                              └────────┬───────┘
                                       │ Create Lead
                                       ▼
                              ┌────────────────┐
                              │  Background    │
                              │  Task (5-15s)  │
                              └────────┬───────┘
                                       │ Send SMS
                                       ▼
┌──────────────┐               ┌───────────────┐
│  Customer    │◀──SMS─────────│  SMS Webhook  │
│  Replies     │               │  (FastAPI)    │
└──────┬───────┘               └───────────────┘
       │                              │
       │ "basement flooded"           │ Emergency?
       └─────────────────────────────▶│ ──Yes──▶ Alert Owner
                                      │
                                      │ ──No───▶ Next Step
                                      ▼
                              ┌────────────────┐
                              │  Intake Logic  │
                              │  Q1 → Q2 → Q3  │
                              └────────┬───────┘
                                       │ Completed
                                       ▼
                              ┌────────────────┐
                              │  Send Calendar │
                              │  Booking Link  │
                              └────────────────┘
```

**Note:** Works with either Twilio or CallRail tracking numbers—same intake flow regardless of provider.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env - use placeholders for local testing, real values for production
```

### 3. Seed Demo Data

```bash
PYTHONPATH=. python scripts/seed_db.py
```

Creates demo shop with tracking number `+15555550100`.

### 4. Run Server

```bash
PYTHONPATH=. python -m app.main
```

Server starts at `http://0.0.0.0:8000`

- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### 5. Run Tests

```bash
PYTHONPATH=. pytest tests/ -v
```

Expected: 27 tests passing (intake logic + CallRail webhooks + owner notifications + e2e smoke tests). See [Testing](#testing) section for details.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info and available endpoints |
| `/health` | GET | Health check (returns `{"status":"ok"}`) |
| `/webhooks/twilio/voice` | POST | Twilio voice webhook (missed call detection) |
| `/webhooks/twilio/sms` | POST | Twilio SMS webhook (inbound message handling) |
| `/webhooks/callrail/call` | POST | CallRail call webhook (missed call detection) |
| `/webhooks/callrail/sms` | POST | CallRail SMS webhook (inbound message handling) |
| `/docs` | GET | Interactive API documentation (Swagger UI) |

## Key Features

✅ **10-Minute Caller Dedupe** – Same number within 10 minutes reuses existing lead  
✅ **Emergency Detection** – Deterministic keyword matching (no LLM required)  
✅ **Owner Alerts** – Immediate SMS to owner on emergency keyword detection  
✅ **Quiet Hours Enforcement** – Configurable per-shop, emergencies always send  
✅ **Three-Step Intake** – Area/Problem → Name → Calendar link  
✅ **STOP/HELP Compliance** – Standard SMS opt-out handling  
✅ **Comprehensive Logging** – All messages logged to `message_logs` table  
✅ **Multi-Provider Support** – Works with Twilio or CallRail  
✅ **$0 Interim Owner Notifications** – Notify shop owners via Slack and/or email when missed calls arrive (NEW)

## Owner Notification System (Interim $0 Path)

For scenarios where SMS to the caller may not be desirable or cost-effective, the system now supports **owner notifications** via Slack and email when a missed call arrives.

### Features

- **Slack Notifications** – Send instant alerts to a Slack channel via incoming webhook
- **Email Notifications** – Send HTML email alerts via Resend API (optional)
- **SMS Fallback** – Original SMS-to-caller flow remains available and can be enabled/disabled via environment variable
- **Idempotent** – Prevents duplicate notifications for the same call_id even if webhooks retry
- **Zero Cost** – Uses free Slack webhooks and optional email (Resend free tier: 100 emails/day)

### Configuration

Set these environment variables to enable owner notifications:

```bash
# Disable SMS to caller (optional, recommended for cost savings)
INTERIM_NO_SMS=true

# Slack incoming webhook URL
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Email notification (optional, requires Resend API key)
OWNER_NOTIFY_EMAIL=owner@example.com
RESEND_API_KEY=re_your_api_key_here

# Custom callback phone number (optional, shown in notifications)
OWNER_CALLBACK_PHONE=+15551234567
```

### Notification Content

Both Slack and email notifications include:
- **Shop name** – Which business received the call
- **Caller number** – Customer's phone number (E.164 format)
- **Tracking number** – Which tracking number was called
- **Timestamp** – When the call occurred (UTC)
- **Call-back CTA** – Clear prompt to call the customer back
- **Lead ID** – Internal tracking ID for reference

### How It Works

1. **Missed Call Detected** – Voice webhook (Twilio or CallRail) creates a lead
2. **Background Task Triggered** – Runs after 5-15s delay
3. **Check SMS Config** – If `INTERIM_NO_SMS=true`, skip SMS to caller
4. **Send Owner Notification** – Slack and/or email alert sent immediately
5. **Idempotency Check** – `owner_notified` flag prevents duplicate alerts

### Slack Message Example

```
📞 Missed Call Alert

Shop: Speed-to-Lead Demo
Time: 2024-09-12 10:30 AM UTC
Caller: +15559876543
Tracking #: +15551234567

🔔 Call them back: +15551234567

Lead ID: lead-uuid-here
```

### Email HTML Example

Subject: `Missed Call Alert - Speed-to-Lead Demo`

- Clean HTML template with caller info
- Clickable phone number link (`tel:` protocol)
- Same information as Slack message
- Plain text fallback included

### Testing

The notification system includes comprehensive unit tests:

```bash
PYTHONPATH=. pytest tests/test_owner_notifications.py -v
```

14 tests covering:
- Slack webhook success/failure
- Email API success/failure
- Missing credentials handling
- Exception handling
- Idempotency
- Environment variable flags

## What's NOT Included

Per design requirements, this system does **not** include:

- LLM-based natural language parsing (deterministic logic only)
- Auto-outreach campaigns
- Third-party CRM integrations (Instantly, HighLevel, etc.)
- 10DLC compliance setup (assume business already configured)

## Project Structure

```
speed-to-lead-sms/
├── app/
│   ├── main.py                      # FastAPI app + startup
│   ├── config.py                    # Settings (env vars)
│   ├── database.py                  # SQLAlchemy setup
│   ├── startup.py                   # Auto-create shop from env vars
│   ├── models/
│   │   └── __init__.py              # DB schema: shops, leads, message_logs
│   ├── routers/
│   │   ├── voice_webhook.py         # POST /webhooks/twilio/voice
│   │   ├── sms_webhook.py           # POST /webhooks/twilio/sms
│   │   └── callrail_webhook.py      # POST /webhooks/callrail/{call,sms}
│   └── services/
│       ├── intake_logic.py          # Keywords, quiet hours, state machine
│       ├── twilio_service.py        # Twilio SMS send, signature validation
│       ├── callrail_service.py      # CallRail SMS send
│       ├── sms_sender.py            # Multi-provider SMS abstraction
│       ├── owner_notifications.py   # Slack + email notifications (NEW)
│       └── background_tasks.py      # Delayed initial SMS + owner alerts
├── scripts/
│   ├── seed_db.py                   # Create demo shop
│   └── generate_friday_audit.py     # Weekly intake report CLI
├── tests/
│   ├── test_intake.py               # Intake logic unit tests
│   ├── test_callrail.py             # CallRail webhook tests
│   └── test_e2e_smoke.py            # End-to-end smoke tests
├── docs/
│   ├── README.md                    # Internal docs index
│   ├── PRODUCTION_STEPS.md          # Detailed deployment steps
│   └── TEST_RESULTS.md              # Test run transcripts
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Dev/test dependencies
├── render.yaml                      # Render.com deployment config
├── .env.example                     # Environment variable template
├── .gitignore                       # Excludes .env, *.db, __pycache__
└── LICENSE                          # ISC License
```

## Database Schema

### `shops`
- `id` (UUID, PK)
- `name` (VARCHAR)
- `twilio_tracking_number` (VARCHAR, unique, E.164 format)
- `owner_cell_number` (VARCHAR, E.164 format)
- `booking_calendar_link` (TEXT)
- `emergency_keywords` (JSON array, default: `["burst","flood","no heat",...]`)
- `quiet_hours_start` / `quiet_hours_end` (VARCHAR, HH:MM format)
- `timezone` (VARCHAR, default: `America/Los_Angeles`)
- `is_active` (BOOLEAN)

### `leads`
- `id` (UUID, PK)
- `shop_id` (UUID, FK → shops)
- `caller_number` (VARCHAR, E.164, indexed)
- `call_sid` (VARCHAR, unique)
- `status` (ENUM: NEW, SMS_SENT, IN_INTAKE, COMPLETED, EMERGENCY_PINGED, OPTED_OUT, etc.)
- `current_step` (INTEGER: 0=Initial, 1=Awaiting Area/Problem, 2=Awaiting Name, 3=Finished)
- `customer_name`, `area_neighborhood`, `problem_description` (nullable TEXT)
- `is_emergency` (BOOLEAN)
- `owner_notified` (BOOLEAN, default: false) – NEW: Tracks if owner notification sent
- `created_at`, `updated_at` (TIMESTAMP UTC)

### `message_logs`
- `id` (INTEGER, PK, auto)
- `lead_id` (UUID, FK → leads, indexed)
- `direction` (ENUM: OUTBOUND, INBOUND)
- `body` (TEXT)
- `twilio_message_sid` (VARCHAR, nullable)
- `created_at` (TIMESTAMP UTC)

## Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for full production deployment guide covering:

- Render.com (recommended, free tier available)
- Railway
- Fly.io
- Twilio webhook configuration
- PostgreSQL migration
- Environment variable reference
- Troubleshooting

**Quick Deploy to Render**:
1. Push to GitHub
2. Create Web Service + PostgreSQL on Render
3. Set environment variables
4. Deploy automatically via `render.yaml`
5. Configure Twilio webhooks to your Render URL

## CallRail Configuration

### Enable CallRail as SMS Provider

Set environment variable:
```bash
SMS_PROVIDER=callrail
```

### CallRail API Credentials

1. Log into [CallRail Dashboard](https://app.callrail.com/)
2. Go to **Settings → API** (https://app.callrail.com/settings/api)
3. Create an API token or use existing token
4. Find your Account ID (in URL: `app.callrail.com/a/{ACCOUNT_ID}/...`)
5. Find your Company ID (in URL when viewing company: `app.callrail.com/a/{ACCOUNT_ID}/companies/{COMPANY_ID}`)

Set environment variables:
```bash
CALLRAIL_API_KEY=your_api_key_here
CALLRAIL_ACCOUNT_ID=your_account_id_here
CALLRAIL_COMPANY_ID=your_company_id_here
```

### CallRail Webhook Configuration

In CallRail Dashboard:

1. Go to **Settings → Integrations → Webhooks**
2. Create two webhooks:

**Post-Call Webhook:**
- **Webhook URL**: `https://your-domain.com/webhooks/callrail/call`
- **Events**: Select "Post-Call" (fires after call completes)
- **Format**: JSON

**Text Message Received Webhook:**
- **Webhook URL**: `https://your-domain.com/webhooks/callrail/sms`
- **Events**: Select "Text Message Received"
- **Format**: JSON

**Note**: The shop lookup uses the `twilio_tracking_number` field for both Twilio and CallRail tracking numbers. No schema changes needed.

## Testing

### Run All Tests

```bash
PYTHONPATH=. pytest tests/ -v
```

**27 tests total** covering:
- Intake logic (emergency keywords, opt-out, HELP, quiet hours, state machine, dedupe)
- CallRail webhooks (missed calls, SMS intake flow, emergency detection, opt-out)
- Owner notifications (Slack, email, idempotency, error handling) – NEW
- End-to-end smoke tests

### Run End-to-End Smoke Tests

```bash
PYTHONPATH=. python tests/test_e2e_smoke.py
```

Simulates:
1. STOP keyword (opt-out)
2. Emergency keyword (owner alert)
3. Normal intake flow (area → name → booking link)
4. 10-minute caller dedupe

### Manual Testing

See **[docs/TEST_RESULTS.md](docs/TEST_RESULTS.md)** for detailed curl examples and expected responses.

## Weekly Audit Report

Generate intake metrics for a date range:

```bash
PYTHONPATH=. python scripts/generate_friday_audit.py \
  --shop-id=<uuid> \
  --start-date=2024-09-01 \
  --end-date=2024-09-07
```

**Output example**:
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

## Security & Privacy

- **Twilio Signature Validation** – Twilio webhooks validate `X-Twilio-Signature` header
- **CallRail Webhooks** – Currently rely on unguessable URL + provider trust (no signature validation implemented)
- **Environment Variables Only** – No secrets in code or version control
- **Secure Database** – PostgreSQL with SSL in production
- **E.164 Phone Format** – Enforced for all phone numbers
- **TCPA Compliance** – STOP/HELP handling per SMS best practices

## Production Checklist

Before going live:

- [ ] PostgreSQL database configured (not SQLite)
- [ ] `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` set (or CallRail credentials)
- [ ] `TWILIO_TRACKING_NUMBER` configured in environment
- [ ] Twilio voice webhook URL configured (or CallRail)
- [ ] Twilio SMS webhook URL configured (or CallRail)
- [ ] Owner cell number verified
- [ ] Calendar booking link tested
- [ ] Emergency keywords customized for business
- [ ] Quiet hours set correctly
- [ ] All tests passing (`pytest tests/ -v`)
- [ ] Health check returns OK

## Why This Stack?

- **FastAPI** – Modern, fast, automatic API docs, excellent async support
- **SQLAlchemy 2.0** – Type-safe ORM with PostgreSQL production support
- **Twilio/CallRail** – Industry-standard SMS/voice APIs, reliable webhooks
- **Render** – Simple deployment, free tier, automatic PostgreSQL
- **No LLM** – Deterministic logic keeps costs near-zero and latency low

## Development Notes

### Add a New Shop

```python
from app.database import SessionLocal
from app.models import Shop
import uuid

db = SessionLocal()
shop = Shop(
    id=str(uuid.uuid4()),
    name="ABC Heating & Cooling",
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
completed_leads = db.query(Lead).filter(
    Lead.status == LeadStatus.COMPLETED
).all()

for lead in completed_leads:
    print(f"{lead.customer_name}: {lead.problem_description}")
```

## License

ISC

## Contributing

This is a portfolio project demonstrating production-ready Python backend development. Issues and pull requests welcome for bug fixes or feature enhancements.

## Author

**Gilbert Bloodsaw** ([4ourCEo](https://github.com/4ourCEo))  
Seattle, WA  
Built as part of OpenClassrooms Application Developer apprenticeship portfolio

## Related Projects

- **[NeatClock](https://neatclock.pro)** – Separate portfolio project: recurring calendar event generator (.ics file creator) built with React + Vite. Not related to this SMS intake engine.
