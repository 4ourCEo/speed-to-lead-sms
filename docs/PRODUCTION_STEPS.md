# Production Deployment - Final Steps

This FastAPI application is ready for production deployment. Follow these steps to go live.

---

## Prerequisites

- Python 3.12+
- Twilio account with phone number
- PostgreSQL database (production) or SQLite (local demo)
- Cal.com calendar link for bookings

---

## Step 1: Install Dependencies

```bash
pip3 install -r requirements.txt
```

---

## Step 2: Configure Environment Variables

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Database (SQLite for local, Postgres for production)
DATABASE_URL=sqlite:///./hvac_intake.db
# Or: DATABASE_URL=postgresql://user:pass@host:5432/hvac_intake

# Twilio (from https://console.twilio.com)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here

# Server
DEBUG=false
HOST=0.0.0.0
PORT=8000
```

---

## Step 3: Initialize Database

```bash
PYTHONPATH=/workspace python3 -c "from app.database import engine, Base; from app.models import *; Base.metadata.create_all(bind=engine)"
```

---

## Step 4: Seed Demo Shop (or create your own)

```bash
PYTHONPATH=/workspace python3 scripts/seed_db.py
```

This creates:
- **Shop Name**: Demo HVAC Company
- **Tracking Number**: +15555550100
- **Owner Cell**: +15555550199
- **Calendar**: https://cal.com/demo-hvac/15min

**To create your own shop:**
Edit `scripts/seed_db.py` with your details before running.

---

## Step 5: Start Server

```bash
PYTHONPATH=/workspace python3 -m app.main
```

Server runs at: `http://0.0.0.0:8000`

Check health:
```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

---

## Step 6: Configure Twilio Webhooks

### Voice Webhook (Missed Calls)

1. Go to [Twilio Console → Phone Numbers](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming)
2. Click your phone number
3. Under **Voice Configuration**:
   - **A CALL COMES IN**: Webhook
   - **URL**: `https://your-domain.com/webhooks/twilio/voice`
   - **HTTP Method**: POST
4. Click **Save**

### SMS Webhook (Replies)

Same page, under **Messaging Configuration**:

1. **A MESSAGE COMES IN**: Webhook
2. **URL**: `https://your-domain.com/webhooks/twilio/sms`
3. **HTTP Method**: POST
4. Click **Save configuration**

---

## Step 7: Three-Message Smoke Test

### Test 1: STOP Keyword (Opt-Out)

**Action:** Send SMS to your Twilio number:
```
STOP
```

**Expected Response:**
```
You have been unsubscribed. You will not receive further messages.
```

**Verify:**
- Lead status set to `OPTED_OUT`
- No further bot messages sent to this number

---

### Test 2: Emergency Keyword

**Setup:** First, trigger a missed call to create a lead and receive initial SMS.

**Action:** Reply with emergency keyword:
```
basement is flooded
```

**Expected:**
1. **User receives:**
   ```
   Thanks. We have flagged this as an urgent priority for our on-call tech. 
   What is your full name?
   ```

2. **Owner receives SMS at configured `owner_cell_number`:**
   ```
   [PRIORITY LEAD ALERT - Demo HVAC Company] Potential emergency reported 
   from +15551234567: 'basement is flooded'. Call back immediately.
   ```

3. **Server logs show:**
   ```
   🚨 EMERGENCY: Sent owner alert for lead <uuid>
   ```

**Verify:**
- Lead flagged with `is_emergency=True`
- Lead status: `EMERGENCY_PINGED`
- Owner SMS sent (check owner phone or server logs)

---

### Test 3: Normal Intake Flow

**From a different phone number:**

#### 3a. Trigger Missed Call

**Action:** Call your Twilio number, let it ring, then hang up.

**Expected:**
- After 5-15 seconds, receive SMS:
  ```
  Demo HVAC Company: Sorry we missed your call. What area are you in, 
  and what issue are you running into? Reply STOP to cancel.
  ```

**Verify:**
- Lead created with status `NEW`
- Lead status updated to `SMS_SENT`
- `current_step=1`

#### 3b. Reply with Area & Problem

**Action:** Reply to SMS:
```
Living room AC not cooling
```

**Expected Response:**
```
Got it. What is your full name?
```

**Verify:**
- Lead status: `IN_INTAKE`
- `current_step=2`
- `problem_description` saved

#### 3c. Provide Name

**Action:** Reply with name:
```
John Smith
```

**Expected Response:**
```
Thanks, John Smith! Book your appointment here: https://cal.com/demo-hvac/15min
```

**Verify:**
- Lead status: `COMPLETED`
- `current_step=3`
- `customer_name="John Smith"`
- Calendar link sent

---

## Step 8: Test Friday Audit

```bash
PYTHONPATH=/workspace python3 scripts/generate_friday_audit.py \
  --shop-id=<your-shop-uuid> \
  --start-date=2024-09-01 \
  --end-date=2024-09-07
```

**Expected Output:**
```
============================================================
WEEKLY INTAKE AUDIT: Demo HVAC Company
============================================================
Dates: 2024-09-01 to 2024-09-07

• Unanswered Calls Ingested: 3
• Immediate SMS Sent: 3
• Intake Form / Text Completed: 2
• Estimates Booked / Links Sent: 2
• Emergency Priority Pings Sent: 1
• Unresponsive / Spam / Dead: 0
• Flagged Carrier Failures / Opt-Outs: 0
============================================================
```

Get shop UUID:
```bash
sqlite3 hvac_intake.db "SELECT id, name FROM shops;"
```

---

## Production Checklist

Before going live:

- [ ] PostgreSQL database configured (not SQLite)
- [ ] Twilio credentials set in environment
- [ ] Twilio voice webhook URL configured
- [ ] Twilio SMS webhook URL configured
- [ ] Demo shop replaced with real shop data
- [ ] Owner cell number verified
- [ ] Calendar booking link tested
- [ ] Emergency keywords customized for business
- [ ] Quiet hours set correctly
- [ ] All three smoke tests passed
- [ ] Server running and health check returns OK
- [ ] Friday audit script tested

---

## Troubleshooting

### Voice webhook not triggering

**Check:**
1. Twilio webhook URL is correct (https://)
2. Server is accessible from public internet
3. HTTP method is POST
4. Check Twilio debugger: https://console.twilio.com/us1/monitor/logs/debugger

### SMS not sending

**Check:**
1. `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` in `.env`
2. Server logs for error messages
3. Twilio SMS logs: https://console.twilio.com/us1/monitor/logs/sms

**Local testing without Twilio:**
- Leave Twilio env vars empty
- Server will print mock SMS to console: `[MOCK SMS] To: +1555...`

### Emergency alerts not sending

**Check:**
1. Emergency keywords configured correctly in shop
2. Message contains exact keyword (case-insensitive substring match)
3. Owner cell number in E.164 format (+15551234567)

### Quiet hours not working

**Check:**
1. Shop timezone set correctly
2. Quiet hours format: "HH:MM" (24-hour)
3. Emergency messages bypass quiet hours (expected behavior)

---

## Monitoring

### View All Leads

```bash
sqlite3 hvac_intake.db "SELECT caller_number, status, customer_name, created_at FROM leads ORDER BY created_at DESC LIMIT 10;"
```

### View Message Logs

```bash
sqlite3 hvac_intake.db "SELECT direction, body, created_at FROM message_logs WHERE lead_id='<uuid>' ORDER BY created_at;"
```

### Real-time Logs

```bash
# Watch server output
tail -f server.log

# Or run server in foreground
PYTHONPATH=/workspace python3 -m app.main
```

---

## Production Deployment Options

### Render.com

1. Create new Web Service
2. Connect GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python3 -m app.main`
5. Add environment variables in dashboard
6. Create PostgreSQL database, copy `DATABASE_URL`

### Railway

1. Create new project
2. Add GitHub repo
3. Add PostgreSQL service
4. Set environment variables
5. Railway auto-detects FastAPI

### Fly.io

1. `fly launch`
2. Add PostgreSQL: `fly postgres create`
3. Set secrets: `fly secrets set TWILIO_ACCOUNT_SID=...`
4. Deploy: `fly deploy`

---

## Next Steps After Deployment

1. **Monitor first week**: Watch message logs, check completion rates
2. **Tune emergency keywords**: Add/remove based on false positives
3. **Adjust quiet hours**: Match business operating hours
4. **Set up weekly audit**: Schedule Friday audit script via cron
5. **Add more shops**: Use same database, separate tracking numbers

---

🎉 **You're live!** Customers can now call your number, and the system will automatically handle intake.
