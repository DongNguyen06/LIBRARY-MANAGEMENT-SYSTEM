"""Admin dashboard and system configuration routes.

This module handles admin-specific operations including system configuration,
log management, and administrative notifications.
"""
import csv
from io import StringIO

from flask import Blueprint, flash, make_response, redirect, render_template, request, session, url_for

from models.admin import Admin
from models.system_config import SystemConfig
from models.system_log import SystemLog
from utils.decorators import login_required, role_required

# Create admin blueprint
admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/dashboard')
@login_required
@role_required('admin')
def dashboard():
    """Display admin dashboard with system statistics and logs.
    
    Returns:
        Rendered admin dashboard template.
    """
    admin = Admin.get_by_id(session['user_id'])
    
    return render_template(
        'pages/admin/dashboard.html',
        stats=admin.get_stats(),
        config=SystemConfig.get(),
        logs=SystemLog.get_recent(50),
        trends=[]  # Can be populated with actual trend data
    )


@admin_bp.route('/config/save', methods=['POST'])
@login_required
@role_required('admin')
def save_config():
    """Save system configuration settings.
    
    Form data:
        max_borrowed_books: Maximum books per user.
        borrow_duration: Default borrow period in days.
        reservation_hold_time: Reservation hold time in days.
        renewal_limit: Maximum number of renewals allowed.
    
    Returns:
        Redirect to admin dashboard with status message.
    """
    admin = Admin.get_by_id(session['user_id'])
    
    config_data = {
        'max_borrowed_books': int(request.form.get('max_borrowed_books', 3)),
        'borrow_duration': int(request.form.get('borrow_duration', 14)),
        'reservation_hold_time': int(request.form.get('reservation_hold_time', 3)),
        'renewal_limit': int(request.form.get('renewal_limit', 2))
    }
    
    success, message = admin.save_system_config(config_data)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/logs/clear', methods=['POST'])
@login_required
@role_required('admin')
def clear_logs():
    """Clear old system logs.
    
    Form data:
        days: Number of days of logs to keep (delete older).
    
    Returns:
        Redirect to admin dashboard with status message.
    """
    admin = Admin.get_by_id(session['user_id'])
    days = int(request.form.get('days', 30))
    
    success, message = admin.clear_system_logs(days)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/send-notifications')
@login_required
@role_required('admin')
def send_notifications():
    """Display notification sending page for admin.
    
    ✅ FIXED: Now supports saving notification templates
    
    Returns:
        Rendered notification sending template.
    """
    return render_template('pages/admin/send_notifications.html')


# ✅ NEW: Add support for notification templates
@admin_bp.route('/notification-templates', methods=['GET'])
@login_required
@role_required('admin')
def list_notification_templates():
    """Get list of notification templates.
    
    Returns:
        JSON list of templates
    """
    from flask import jsonify
    
    # ✅ FIXED: Define built-in templates
    templates = [
        {
            'id': 'overdue_reminder',
            'name': 'Overdue Book Reminder',
            'title': 'Overdue Book Reminder',
            'message': 'Please return your overdue books to avoid late fees.',
            'type': 'warning'
        },
        {
            'id': 'maintenance',
            'name': 'System Maintenance Notice',
            'title': 'System Maintenance',
            'message': 'The library system will undergo maintenance on [DATE].',
            'type': 'info'
        },
        {
            'id': 'event',
            'name': 'Library Event',
            'title': 'Library Event Announcement',
            'message': 'Join us for our upcoming library event!',
            'type': 'success'
        },
        {
            'id': 'urgent',
            'name': 'Urgent Notice',
            'title': 'Urgent: Account Issue',
            'message': 'Please contact the library staff immediately regarding your account.',
            'type': 'urgent'
        },
        {
            'id': 'available',
            'name': 'Book Available',
            'title': 'Reserved Book Available',
            'message': 'Your reserved book is now available for pickup!',
            'type': 'success'
        }
    ]
    
    return jsonify({
        'success': True,
        'templates': templates
    })


@admin_bp.route('/logs/export')
@login_required
@role_required('admin')
def export_logs():
    """Export system logs to CSV file.
    
    Returns:
        CSV file download response containing system logs.
    """
    logs = SystemLog.get_recent(1000)
    
    # Create CSV in memory
    si = StringIO()
    writer = csv.writer(si)
    
    # Write header
    writer.writerow(['Timestamp', 'Action', 'Details', 'Type', 'User ID'])
    
    # Write log data
    for log in logs:
        writer.writerow([
            log['timestamp'],
            log['action'],
            log['details'],
            log['log_type'],
            log.get('user_id', '')
        ])
    
    # Create response with CSV data
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=system_logs.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output