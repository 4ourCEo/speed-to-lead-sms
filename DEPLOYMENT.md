# Deployment Guide

This guide covers deploying the HVAC SMS webhook worker to Cloudflare Workers.

## Prerequisites

- [Node.js](https://nodejs.org/) 18+ installed
- [Cloudflare account](https://dash.cloudflare.com/sign-up) (free tier works)
- [Twilio account](https://www.twilio.com/try-twilio) with a phone number
- [xAI API key](https://x.ai/) for Grok access

## Initial Setup

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd hvac-sms-webhook
npm install
```

### 2. Authenticate with Cloudflare

```bash
npx wrangler login
```

This opens a browser window to authorize Wrangler with your Cloudflare account.

### 3. Configure Secrets

Set all required environment variables as Cloudflare secrets:

```bash
# Twilio configuration
npx wrangler secret put TWILIO_AUTH_TOKEN
# Paste your Twilio auth token (found at twilio.com/console)

# xAI configuration
npx wrangler secret put XAI_API_KEY
# Paste your xAI API key (from x.ai)

# Shop configuration
npx wrangler secret put SHOP_NAME
# e.g., "ABC Heating & Cooling"

npx wrangler secret put SHOP_CALENDAR_URL
# e.g., "https://cal.com/abc-hvac/15min"

npx wrangler secret put SHOP_OWNER_CELL
# e.g., "+15551234567" (E.164 format)

# Optional: Quiet hours (defaults to 09:00-21:00 ET)
npx wrangler secret put SHOP_QUIET_HOURS_START
# e.g., "09:00"

npx wrangler secret put SHOP_QUIET_HOURS_END
# e.g., "21:00"

npx wrangler secret put SHOP_TIMEZONE
# e.g., "America/New_York"

# Optional: Custom emergency keywords
npx wrangler secret put EMERGENCY_KEYWORDS
# e.g., "no heat,flooded,gas leak"
```

## Deploy to Production

### First Deployment

```bash
npm run deploy
```

This command:
1. Compiles TypeScript
2. Bundles the worker
3. Creates the Durable Object namespace
4. Deploys to Cloudflare's edge network

You'll see output like:

```
Published hvac-sms-webhook (1.23 sec)
  https://hvac-sms-webhook.<your-subdomain>.workers.dev
Current Deployment ID: <deployment-id>
```

**Save this URL** - you'll need it for Twilio configuration.

### Subsequent Deployments

Just run `npm run deploy` again. Cloudflare automatically:
- Deploys the new version
- Routes traffic gradually (canary deployment)
- Rolls back automatically if errors spike

## Twilio Configuration

### 1. Configure Webhook URL

1. Go to [Twilio Console → Phone Numbers](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming)
2. Click your phone number
3. Scroll to "Messaging Configuration"
4. Set "A MESSAGE COMES IN" to:
   - **Webhook**: `https://hvac-sms-webhook.<your-subdomain>.workers.dev/webhook/sms`
   - **HTTP Method**: POST
5. Click "Save"

### 2. Test the Integration

Send a text message to your Twilio number:

```
"Living room has no heat"
```

You should receive a response from the bot asking for details.

### 3. Monitor Webhook Activity

View real-time webhook logs:

```bash
npx wrangler tail
```

This streams live logs from your worker, useful for debugging.

## Monitoring

### Cloudflare Dashboard

1. Go to [Cloudflare Dashboard → Workers](https://dash.cloudflare.com/)
2. Click "hvac-sms-webhook"
3. View:
   - Request volume
   - Error rates
   - Latency (p50, p99)
   - Durable Object metrics

### Health Check

Test the worker is running:

```bash
curl https://hvac-sms-webhook.<your-subdomain>.workers.dev/health
```

Expected response:
```json
{
  "status": "ok",
  "timestamp": 1694392800000
}
```

## Troubleshooting

### Signature Validation Failures

**Symptom**: All webhooks return 401 Unauthorized

**Solution**: Verify TWILIO_AUTH_TOKEN is correct:

```bash
npx wrangler secret list
# Check if TWILIO_AUTH_TOKEN is set

# Update if needed
npx wrangler secret put TWILIO_AUTH_TOKEN
```

### Grok API Errors

**Symptom**: Bot doesn't respond or returns error message

**Solution**: Check XAI_API_KEY:

```bash
# Verify secret is set
npx wrangler secret list

# Test Grok API manually
curl https://api.x.ai/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"grok-4.6","messages":[{"role":"user","content":"test"}]}'
```

### State Not Persisting

**Symptom**: Bot always asks the same question

**Solution**: Ensure Durable Objects migration ran:

```bash
# Redeploy to apply migrations
npm run deploy
```

### Deploy Failures

**Symptom**: `wrangler deploy` fails

**Common causes**:
- Not logged in: Run `npx wrangler login`
- Syntax errors: Run `npm test` locally first
- Missing secrets: Set all required secrets (see step 3)

## Rollback

If a deployment has issues, rollback to the previous version:

```bash
# List recent deployments
npx wrangler deployments list

# Rollback to specific deployment
npx wrangler rollback <deployment-id>
```

## Custom Domain (Optional)

To use a custom domain like `sms.yourdomain.com`:

1. Add domain to Cloudflare (if not already)
2. Add a route in Wrangler config:

```toml
# wrangler.toml
routes = [
  { pattern = "sms.yourdomain.com/webhook/sms", zone_name = "yourdomain.com" }
]
```

3. Deploy: `npm run deploy`
4. Update Twilio webhook URL to use custom domain

## Costs

### Free Tier (included)

- 100,000 requests/day
- 10ms CPU time per request
- Durable Objects: 1GB storage + 1M requests

### Beyond Free Tier

- Workers: $5/month for 10M requests
- Durable Objects: $0.15 per million requests
- Storage: $0.20 per GB-month

**Typical usage**: A shop handling 50 SMS/day stays well within free tier.

## Security Best Practices

1. **Never commit secrets**: Use `wrangler secret put`
2. **Keep TWILIO_AUTH_TOKEN secure**: Enables signature validation
3. **Rotate XAI_API_KEY periodically**: Update via `wrangler secret put`
4. **Monitor logs**: Watch for suspicious activity via `wrangler tail`

## Support

- **Cloudflare Workers**: https://developers.cloudflare.com/workers/
- **Twilio Webhooks**: https://www.twilio.com/docs/usage/webhooks
- **xAI API**: https://docs.x.ai/

## Production Checklist

Before going live:

- [ ] All secrets configured in Cloudflare
- [ ] Deployed to production (`npm run deploy`)
- [ ] Twilio webhook URL configured
- [ ] Health check passes
- [ ] Test STOP keyword works
- [ ] Test emergency keywords trigger owner notification
- [ ] Verify quiet hours enforcement
- [ ] Test full conversation flow (Q1 → Q2 → calendar)
- [ ] Monitor logs for first few real conversations
- [ ] Backup event data strategy in place

## Next Steps

After successful deployment:

1. Monitor first week of usage via Cloudflare dashboard
2. Review event logs to tune keyword detection
3. Adjust quiet hours based on actual call patterns
4. Consider adding analytics dashboard (query Durable Object events)
5. Set up alerts for error rate spikes (Cloudflare Notifications)
