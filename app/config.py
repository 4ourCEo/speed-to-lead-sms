from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./hvac_intake.db"
    
    # Twilio
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    
    # Startup Shop Configuration (for ephemeral/production deployments)
    shop_name: str = "Speed-to-Lead Demo"
    twilio_tracking_number: Optional[str] = None
    shop_owner_cell: Optional[str] = None
    booking_calendar_link: str = "https://cal.com/demo"
    
    # Server
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
