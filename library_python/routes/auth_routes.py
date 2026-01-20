"""Authentication routes for the library management system.

This module handles user authentication including login, registration,
logout, and password recovery.
"""
from typing import Optional

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for
)

from models.user import User

# Create authentication blueprint
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login.
    
    GET: Display login form.
    POST: Process login credentials and create session.
    
    Returns:
        Rendered template or redirect response.
    """
    if request.method == 'POST':
        email: str = request.form.get('email', '').strip()
        password: str = request.form.get('password', '')
        remember: bool = request.form.get('remember') == 'on'

        user: Optional[User] = User.login(email, password)
        
        if user:
            # Create user session
            session['user_id'] = user.id
            session['user_role'] = user.role
            session.permanent = remember
            
            flash(f'Welcome back, {user.name}!', 'success')

            # Redirect to appropriate dashboard based on role
            next_page = request.args.get('next')
            if user.is_admin():
                return redirect(next_page or url_for('admin.dashboard'))
            elif user.is_staff():
                return redirect(next_page or url_for('staff.dashboard'))
            else:
                return redirect(next_page or url_for('user.dashboard'))
        else:
            flash('Invalid email or password', 'error')

    # GET request - show login form
    remembered_email: str = request.cookies.get('remembered_email', '')
    return render_template('pages/login.html', remembered_email=remembered_email)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new user registration.
    
    GET: Display registration form.
    POST: Create new user account.
    
    Returns:
        Rendered template or redirect response.
    """
    if request.method == 'POST':
        email: str = request.form.get('email', '').strip()
        password: str = request.form.get('password', '')
        name: str = request.form.get('name', '').strip()
        phone: str = request.form.get('phone', '').strip()
        birthday: Optional[str] = request.form.get('birthday')

        user: Optional[User] = User.create(
            email=email,
            password=password,
            name=name,
            phone=phone,
            birthday=birthday
        )
        
        if user:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Registration failed. Email may already exist.', 'error')
            
    return render_template('pages/register.html')


@auth_bp.route('/logout')
def logout():
    """Handle user logout.
    
    Clears the user session and redirects to login page.
    
    Returns:
        Redirect to login page.
    """
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle password reset requests.
    
    GET: Display password reset form.
    POST: Process password reset.
    
    Returns:
        Rendered template or redirect response.
    """
    if request.method == 'POST':
        email: str = request.form.get('email', '').strip()
        new_password: str = request.form.get('new_password', '')
        
        user: Optional[User] = User.get_by_email(email)
        
        if user:
            success, message = user.reset_password(new_password)
            flash(message, 'success' if success else 'error')
        else:
            flash('Email not found', 'error')
            
        return redirect(url_for('auth.login'))
        
    return render_template('pages/forgot_password.html')