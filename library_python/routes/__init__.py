"""Routes package initialization.

This module exports all blueprints for registration in the main app.

Blueprint organization:
    - auth_bp: Authentication (login, register, logout)
    - main_bp: Public pages (home, search, book details)
    - user_bp: User dashboard and profile
    - staff_bp: Staff operations and management
    - admin_bp: Admin dashboard and configuration
    - api_bp: AJAX/JSON API endpoints
"""
from routes.admin_routes import admin_bp
from routes.api_routes import api_bp
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.staff_routes import staff_bp
from routes.user_routes import user_bp

__all__ = [
    'auth_bp',
    'main_bp',
    'user_bp',
    'staff_bp',
    'admin_bp',
    'api_bp',
]