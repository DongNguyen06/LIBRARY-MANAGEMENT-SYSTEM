import os
from datetime import timedelta
from typing import Set


class Config:
    # Secret key for session management and security
    SECRET_KEY: str = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Session configuration
    SESSION_PERMANENT: bool = False
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(days=7)
    
    # Database configuration
    DATABASE_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'data', 'library.db'
    )
    
    # Upload configuration
    UPLOAD_FOLDER: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads'
    )
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS: Set[str] = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Library system business rules
    MAX_BORROW_LIMIT: int = 5  # Maximum books per user
    BORROW_DURATION_DAYS: int = 14  #  14 days
    MAX_RENEWAL_COUNT: int = 1  # Maximum renewals allowed ( only 1 time)
    RENEWAL_EXTENSION_DAYS: int = 7  # Extension period for renewal ( 7 days)
    PENDING_PICKUP_HOURS: int = 48  # Hours to hold book for pickup
    RESERVATION_HOLD_HOURS: int = 48  # Hours to hold for reserver
    GRACE_PERIOD_MINUTES: int = 60  # Grace period before late fee applies
    LATE_FEE_HOURLY: float = 2000.0  # Late fee per hour for delays <24h (VND)
    LATE_FEE_DAILY: float = 10000.0  # Late fee per day for delays >=24h (VND)
    FINE_PER_DAY: float = 10000.0  # Deprecated: use LATE_FEE_DAILY instead