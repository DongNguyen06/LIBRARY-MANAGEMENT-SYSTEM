"""Configuration file for Flask application.

This module contains all configuration settings for the library management system,
including database paths, upload settings, and business rules.
"""
import os
from datetime import timedelta
from typing import Set


class Config:
    """Base configuration class for Flask application.
    
    Contains all application settings including:
    - Session management configuration
    - Database connection settings
    - File upload restrictions
    - Library business rules (borrow limits, fines, etc.)
    
    Attributes:
        SECRET_KEY (str): Secret key for session encryption and CSRF protection.
        SESSION_PERMANENT (bool): Whether sessions should be permanent.
        PERMANENT_SESSION_LIFETIME (timedelta): Duration of permanent sessions.
        DATABASE_PATH (str): Absolute path to SQLite database file.
        UPLOAD_FOLDER (str): Directory path for uploaded files.
        MAX_CONTENT_LENGTH (int): Maximum allowed file size in bytes.
        ALLOWED_EXTENSIONS (Set[str]): Set of allowed file extensions.
        MAX_BORROW_LIMIT (int): Maximum books a user can borrow simultaneously.
        BORROW_DURATION_DAYS (int): Default borrow period in days.
        MAX_RENEWAL_COUNT (int): Maximum times a book can be renewed.
        FINE_PER_DAY (float): Fine amount per day for overdue books.
        MAX_FINE_BEFORE_LOCK (float): Maximum fine before account lock.
        MAX_FINES_BEFORE_LOCK (int): Fines count before account suspension.
    """
    
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
    BORROW_DURATION_DAYS: int = 14  # ✅ FIXED: Changed from 7 to 14 days (SRS requirement)
    MAX_RENEWAL_COUNT: int = 1  # Maximum renewals allowed (SRS: only 1 time)
    RENEWAL_EXTENSION_DAYS: int = 7  # Extension period for renewal (SRS: 7 days)
    PENDING_PICKUP_HOURS: int = 48  # Hours to hold book for pickup
    RESERVATION_HOLD_HOURS: int = 48  # Hours to hold for reserver
    GRACE_PERIOD_MINUTES: int = 60  # Grace period before late fee applies
    LATE_FEE_HOURLY: float = 2000.0  # Late fee per hour for delays <24h (VND)
    LATE_FEE_DAILY: float = 10000.0  # Late fee per day for delays >=24h (VND)
    FINE_PER_DAY: float = 10000.0  # Deprecated: use LATE_FEE_DAILY instead
    MAX_FINE_BEFORE_LOCK: float = 100000.00  # Account lock threshold (VND)
    MAX_FINES_BEFORE_LOCK: int = 3  # Fine count before suspension
    MAX_VIOLATIONS_BEFORE_LOCK: int = MAX_FINES_BEFORE_LOCK  # Alias for backward compatibility