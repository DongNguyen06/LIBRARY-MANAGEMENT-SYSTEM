"""Authentication and authorization decorators.

This module contains decorators for protecting routes and checking user roles.
"""
from functools import wraps
from typing import Callable, Tuple

from flask import flash, redirect, request, session, url_for

from models.user import User


def login_required(f: Callable) -> Callable:
    """Decorator to require user login for a route.
    
    Args:
        f: The function to decorate.
        
    Returns:
        The decorated function that checks authentication.
        
    Example:
        @app.route('/dashboard')
        @login_required
        def dashboard():
            return "Dashboard content"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles: Tuple[str]) -> Callable:
    """Decorator to require specific user roles for a route.
    
    Admin users always have access. Other users must have one of the
    specified roles.
    
    Args:
        *roles: Variable length argument list of role names (e.g., 'user', 'staff').
        
    Returns:
        A decorator function that checks user roles.
        
    Example:
        @app.route('/staff')
        @login_required
        @role_required('staff')
        def staff_page():
            return "Staff content"
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page', 'warning')
                return redirect(url_for('auth.login'))

            user = User.get_by_id(session['user_id'])
            if not user:
                session.clear()
                flash('User not found. Please login again.', 'error')
                return redirect(url_for('auth.login'))

            # Admin users have access to all routes
            if user.is_admin():
                return f(*args, **kwargs)

            # Check if user has one of the required roles
            if user.role in roles:
                return f(*args, **kwargs)

            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('main.home'))
            
        return decorated_function
    return decorator