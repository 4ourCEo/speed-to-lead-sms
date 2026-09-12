from pydantic_settings import BaseSettings
from typing import Optional, Literal


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./hvac_intake.db"
    
    # SMS Provider Selection
    sms_provider: Literal["twilio", "callrail"] = "twilio"
    
    # Twilio
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    
    # CallRail
    callrail_api_key: Optional[str] = None
    callrail_account_id: Optional[str] = None
    callrail_company_id: Optional[str] = None
    
    # Startup Shop Configuration (for ephemeral/production deployments)
    shop_name: str = "Speed-to-Lead Demo"
    twilio_tracking_number: Optional[str] = None
    shop_owner_cell: Optional[str] = None
    booking_calendar_link: str = "https://cal.com/demo"
    
    # Owner Notification Configuration (Interim $0 notification path)
    interim_no_sms: bool = False
    skip_caller_sms: bool = False
    slack_webhook_url: Optional[str] = None
    owner_notify_email: Optional[str] = None
    resend_api_key: Optional[str] = None
    resend_domain: str = "resend.dev"
    owner_callback_phone: Optional[str] = None
    
    # Server
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
