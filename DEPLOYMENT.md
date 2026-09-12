# Deployment Guide

This guide covers deploying the FastAPI application to production hosting platforms.

## Prerequisites

- Python 3.12+
- Twilio account with a phone number ([sign up](https://www.twilio.com/try-twilio))
- PostgreSQL database (for production) or SQLite (for local dev)
- Cal.com or similar booking calendar link

## Platform Options

This application can be deployed to any platform supporting Python web apps. Recommended options:

### Option 1: Render.com (Recommended)

**Pros**: Free tier available, automatic PostgreSQL, simple configuration via `render.yaml`

**Steps:**

1. Push code to GitHub (private or public repository)

2. Create new Web Service on [Render Dashboard](https://dashboard.render.com/)
   - Connect your GitHub repository
   - Render auto-detects settings from `render.yaml`

3. Add PostgreSQL database:
   - Create new PostgreSQL instance in Render
   - Copy the **Internal Database URL** from database info page
   
4. Set environment variables in Render dashboard:
   ```
   DATABASE_URL=<internal-database-url-from-render>
   TWILIO_ACCOUNT_SID=<from-twilio-console>
   TWILIO_AUTH_TOKEN=<from-twilio-console>
   TWILIO_TRACKING_NUMBER=<your-twilio-number-in-e164>
   SHOP_NAME=Your Business Name
   SHOP_OWNER_CELL=<owner-phone-in-e164>
   BOOKING_CALENDAR_LINK=<your-cal-com-link>
   PYTHONPATH=/opt/render/project/src
   ```

5. Deploy - Render will:
   - Run `pip install -r requirements.txt`
   - Start with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Create tables automatically via `app.main.py` startup

6. Note your deployment URL (e.g., `https://your-app.onrender.com`)

### Option 2: Railway

**Pros**: Simple deployment, automatic PostgreSQL provisioning

**Steps:**

1. Install Railway CLI:
   ```bash
   npm i -g @railway/cli
   railway login
   ```

2. Initialize project:
   ```bash
   railway init
   railway add --database postgresql
   ```

3. Set environment variables:
   ```bash
   railway variables set TWILIO_ACCOUNT_SID=<your-sid>
   railway variables set TWILIO_AUTH_TOKEN=<your-token>
   railway variables set TWILIO_TRACKING_NUMBER=<your-number>
   railway variables set SHOP_NAME="Your Business"
   railway variables set SHOP_OWNER_CELL=<your-cell>
   railway variables set BOOKING_CALENDAR_LINK=<your-link>
   ```

4. Deploy:
   ```bash
   railway up
   ```

5. Get deployment URL:
   ```bash
   railway domain
   ```

### Option 3: Fly.io

**Pros**: Global edge deployment, generous free tier

**Steps:**

1. Install Fly CLI and authenticate:
   ```bash
   curl -L https://fly.io/install.sh | sh
   fly auth login
   ```

2. Launch app:
   ```bash
   fly launch
   # Choose app name and region
   # Say NO to PostgreSQL for now (we'll add it separately)
   ```

3. Create PostgreSQL:
   ```bash
   fly postgres create
   fly postgres attach <postgres-app-name>
   ```

4. Set secrets:
   ```bash
   fly secrets set TWILIO_ACCOUNT_SID=<your-sid>
   fly secrets set TWILIO_AUTH_TOKEN=<your-token>
   fly secrets set TWILIO_TRACKING_NUMBER=<your-number>
   fly secrets set SHOP_NAME="Your Business"
   fly secrets set SHOP_OWNER_CELL=<your-cell>
   fly secrets set BOOKING_CALENDAR_LINK=<your-link>
   ```

5. Deploy:
   ```bash
   fly deploy
   ```

## Configure Twilio Webhooks

After deployment, configure Twilio to send webhooks to your app:

### Voice Webhook (Missed Calls)

1. Go to [Twilio Console → Phone Numbers](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming)
2. Select your phone number
3. Under **Voice Configuration**:
   - **A CALL COMES IN**: Webhook
   - **URL**: `https://your-deployment-url.com/webhooks/twilio/voice`
   - **HTTP Method**: POST
4. Click **Save**

### SMS Webhook (Inbound Messages)

Same phone number page, under **Messaging Configuration**:

1. **A MESSAGE COMES IN**: Webhook
2. **URL**: `https://your-deployment-url.com/webhooks/twilio/sms`
3. **HTTP Method**: POST
4. Click **Save configuration**

## Verify Deployment

### 1. Health Check

```bash
curl https://your-deployment-url.com/health
```

Expected: `{"status":"ok"}`

### 2. Check Shop Created

The app automatically creates/updates a shop from environment variables at startup. Check logs for:

```
✓ Created shop: <uuid>
  Name: Your Business
  Tracking: +15551234567
  Owner Cell: +15559876543
  Calendar: https://cal.com/your-link
```

### 3. Test Voice Webhook

Call your Twilio number and hang up after 2-3 rings. You should receive an SMS within 15 seconds.

### 4. Test SMS Flow

Reply to the SMS with your issue (e.g., "Living room AC broken"). The bot should ask for your name, then send a booking link.

## Monitoring & Logs

### Render

View logs in dashboard or via CLI:
```bash
render logs --tail
```

### Railway

```bash
railway logs
```

### Fly.io

```bash
fly logs
```

## Database Migrations

The app uses SQLAlchemy and auto-creates tables at startup (`Base.metadata.create_all`). For schema changes:

1. Update models in `app/models/__init__.py`
2. Redeploy - tables will be updated automatically

**Note**: For production, consider using Alembic for proper migrations to avoid data loss.

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `sqlite:///./hvac_intake.db` | PostgreSQL connection string (production) |
| `SMS_PROVIDER` | No | `twilio` | SMS provider: `twilio` or `callrail` |
| **Twilio Credentials** | | | **Required if SMS_PROVIDER=twilio** |
| `TWILIO_ACCOUNT_SID` | Conditional | - | From Twilio console |
| `TWILIO_AUTH_TOKEN` | Conditional | - | From Twilio console |
| `TWILIO_TRACKING_NUMBER` | Recommended | - | Shop tracking number (E.164) |
| **CallRail Credentials** | | | **Required if SMS_PROVIDER=callrail** |
| `CALLRAIL_API_KEY` | Conditional | - | From CallRail Settings → API |
| `CALLRAIL_ACCOUNT_ID` | Conditional | - | From CallRail dashboard URL |
| `CALLRAIL_COMPANY_ID` | Conditional | - | From CallRail dashboard URL |
| **Shop Configuration** | | | |
| `SHOP_NAME` | No | "Speed-to-Lead Demo" | Business name |
| `SHOP_OWNER_CELL` | No | Same as tracking | Owner emergency contact (E.164) |
| `BOOKING_CALENDAR_LINK` | No | https://cal.com/demo | Booking URL |
| **Server Settings** | | | |
| `PYTHONPATH` | Platform-specific | - | Set to `/opt/render/project/src` on Render |
| `HOST` | No | 0.0.0.0 | Server bind address |
| `PORT` | No | 8000 | Server port (overridden by platform) |
| `DEBUG` | No | false | Debug mode flag |

**Note:** For CallRail webhook configuration (URL setup, event selection), see the CallRail Configuration section in the main [README.md](README.md#callrail-configuration).

## Troubleshooting

### Webhooks Not Triggering

- Verify webhook URLs are correct (https://)
- Check Twilio Debugger: https://console.twilio.com/us1/monitor/logs/debugger
- Ensure app is publicly accessible

### SMS Not Sending

- Check `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are set
- View application logs for error messages
- Check Twilio SMS logs: https://console.twilio.com/us1/monitor/logs/sms

### Database Connection Errors

- Verify `DATABASE_URL` format: `postgresql://user:pass@host:port/dbname`
- Check database is accessible from your deployment
- Review platform-specific database connection docs

### Emergency Alerts Not Working

- Ensure emergency keywords are configured in shop table
- Verify `SHOP_OWNER_CELL` is in E.164 format (+15551234567)
- Check message contains emergency keyword (case-insensitive)

## Production Checklist

Before going live:

- [ ] PostgreSQL database configured (not SQLite)
- [ ] All environment variables set
- [ ] Twilio voice webhook configured
- [ ] Twilio SMS webhook configured
- [ ] Health check returns OK
- [ ] Test call → SMS flow works
- [ ] Test emergency keyword detection
- [ ] Test STOP opt-out handling
- [ ] Owner cell number verified
- [ ] Calendar link tested and working

## Security Best Practices

1. **Never commit secrets** - Use environment variables only
2. **Use PostgreSQL in production** - SQLite resets on platform restarts
3. **Keep dependencies updated** - Run `pip list --outdated` periodically
4. **Monitor logs** - Watch for suspicious activity or errors
5. **Validate Twilio signatures** - Already implemented in `app/services/twilio_service.py`

## Cost Estimates

### Render.com Free Tier

- Web Service: Free (spins down after 15 min inactivity)
- PostgreSQL: Free (90-day expiration, then $7/month)
- Suitable for: Demo, low-volume testing

### Railway

- $5/month credit free
- ~$5-10/month for small production use
- Pay-as-you-go pricing

### Fly.io

- Free tier: 3 shared VMs, 3GB storage
- Suitable for: Small production deployments

### Twilio

- Phone number: ~$1/month
- SMS: $0.0079/message (outbound)
- Voice: $0.013/minute (inbound)

**Example**: 100 calls/month = ~$8/month total (Twilio + hosting)

## Support Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Twilio Webhooks**: https://www.twilio.com/docs/usage/webhooks
- **Render Docs**: https://render.com/docs
- **Railway Docs**: https://docs.railway.app/
- **Fly.io Docs**: https://fly.io/docs/
