## Architecture Deep Dive

### Why Grok Handles ONLY Extraction

**The Problem**: Natural language is messy. Users say:
- "whole house cold" (area + problem in 3 words)
- "upstairs thermostat broken"
- "its freezing down stairs"

**The Solution**: Use Grok to parse into structured data:
```json
{
  "area": "downstairs",
  "problem": "no heat",
  "done": true
}
```

**Why Not Let Grok Decide Everything?**

1. **Cost**: Every LLM call costs money
2. **Latency**: API roundtrip adds 500-1000ms
3. **Reliability**: LLMs can hallucinate or ignore instructions
4. **Compliance**: STOP handling must be deterministic for TCPA

### Deterministic Logic Examples

**STOP detection (keywords.ts)**:
```typescript
if (message.toLowerCase().includes('stop')) {
  // Immediately halt, no LLM involved
}
```

**Emergency detection (keywords.ts)**:
```typescript
const EMERGENCY = ['no heat', 'flooded', 'gas leak'];
if (EMERGENCY.some(kw => message.includes(kw))) {
  // Ping owner, no LLM involved
}
```

**Quiet hours (quiet-hours.ts)**:
```typescript
if (currentTime < 9am || currentTime >= 9pm) {
  // Don't send message, no LLM involved
}
```

### State Machine Flow

```
User: "Living room is cold"
  ↓
[STOP check] → No match
  ↓
[Emergency check] → No match
  ↓
[Quiet hours] → Currently in hours
  ↓
[Load state] → Q1_AREA
  ↓
[Call Grok] → { area: "living room", problem: "cold/no heat", done: true }
  ↓
[State machine] → Both fields present → DONE
  ↓
[Response] → "Perfect! Book here: cal.com/..."
  ↓
[Log event] → Save to Durable Object
```

### Data Flow

```
Twilio → Worker → Validate → Check Keywords → Extract (Grok) → State Machine → Response
                      ↓                             ↓                  ↓
                  [Durable Object: Conversation State + Event Logs]
```

### Event Logging Strategy

Every interaction creates typed events:

```typescript
type EventType = 
  | 'inbound_sms'        // Every message received
  | 'keyword_match'      // STOP detected
  | 'emergency_detected' // Emergency keyword found
  | 'grok_extraction'    // LLM returned data
  | 'state_transition'   // Q1 → Q2 → Done
  | 'calendar_sent'      // Final link delivered
  | 'quiet_hours_skip'   // Message during quiet hours
  | 'error'              // Any failure
```

**Why Not Aggregate Now?**

Raw events let you answer questions like:
- How many users abandon after Q1?
- What % of first messages have both area + problem?
- Which keywords appear most in emergency situations?
- Average messages per conversation before calendar link?

Build Friday reports from raw events, not pre-computed metrics.

### Performance Characteristics

- **Cold start**: ~10ms (Durable Objects warm on first request)
- **Signature validation**: ~5ms (Web Crypto API)
- **Grok API call**: ~500-1000ms (xAI infrastructure)
- **State read/write**: ~5-10ms (Durable Objects)
- **Total latency**: ~600-1100ms typical

Twilio expects webhook responses in <10 seconds, so plenty of headroom.

### Scaling Considerations

**Durable Objects**: One per phone number
- Automatic distribution across Cloudflare's network
- Strong consistency within each conversation
- No coordination needed between phone numbers

**Edge compute**: Worker runs in 300+ data centers
- Requests route to nearest edge
- Durable Objects auto-migrate to common request regions

**Bottleneck**: xAI API rate limits (not Cloudflare)
- Monitor 429 responses from Grok
- Consider retry logic if needed (not implemented yet)

### Security Model

1. **Twilio signature**: Proves request came from Twilio
2. **HTTPS**: All traffic encrypted
3. **Secrets**: Stored in Cloudflare's encrypted KV, never in code
4. **No PII logging**: Phone numbers in events (consider hashing)

### Testing Strategy

**Unit tests**: Deterministic logic only
- Keyword matching
- State transitions
- Quiet hours calculation

**Not tested**: Grok API (external service, test in integration)

**Manual testing**: Use `test-webhook.sh` or Twilio console

**Production monitoring**: `wrangler tail` for live logs
