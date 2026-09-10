from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import voice_webhook, sms_webhook

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HVAC Speed-to-Lead SMS Intake Engine",
    description="Twilio-powered missed call intake system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_webhook.router)
app.include_router(sms_webhook.router)


@app.get("/")
async def root():
    return {
        "service": "HVAC Speed-to-Lead SMS Intake Engine",
        "status": "running",
        "endpoints": {
            "voice_webhook": "/webhooks/twilio/voice",
            "sms_webhook": "/webhooks/twilio/sms"
        }
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    uvicorn.run(app, host=settings.host, port=settings.port)
