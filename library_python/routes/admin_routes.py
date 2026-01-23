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
    """Display admin dashboard with system statistics and logs."""
    admin = Admin.get_by_id(session['user_id'])
    
    return render_template(
        'pages/admin/dashboard.html',
        stats=admin.get_stats(),
        config=SystemConfig.get(),
        logs=SystemLog.get_recent(50),
        trends=[]
    )


@admin_bp.route('/config/save', methods=['POST'])
@login_required
@role_required('admin')
def save_config():
    """Save system configuration settings.
    
    Now includes 'late_fee_per_day' to allow dynamic fine adjustment.
    """
    admin = Admin.get_by_id(session['user_id'])
    
    config_data = {
        'max_borrowed_books': int(request.form.get('max_borrowed_books', 3)),
        'borrow_duration': int(request.form.get('borrow_duration', 14)),
        'reservation_hold_time': int(request.form.get('reservation_hold_time', 3)),
        'renewal_limit': int(request.form.get('renewal_limit', 2)),
        'late_fee_per_day': float(request.form.get('late_fee_per_day', 1000.0))
    }
    
    success, message = admin.save_system_config(config_data)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/logs/clear', methods=['POST'])
@login_required
@role_required('admin')
def clear_logs():
    """Clear old system logs."""
    admin = Admin.get_by_id(session['user_id'])
    days = int(request.form.get('days', 30))
    
    success, message = admin.clear_system_logs(days)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/send-notifications')
@login_required
@role_required('admin')
def send_notifications():
    """Display notification sending page for admin."""
    return render_template('pages/admin/send_notifications.html')


@admin_bp.route('/notification-templates', methods=['GET'])
@login_required
@role_required('admin')
def list_notification_templates():
    """Get list of notification templates."""
    from flask import jsonify
    
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
    """Export system logs to CSV file."""
    logs = SystemLog.get_recent(1000)
    
    si = StringIO()
    writer = csv.writer(si)
    
    writer.writerow(['Timestamp', 'Action', 'Details', 'Type', 'User ID'])
    
    for log in logs:
        writer.writerow([
            log['timestamp'],
            log['action'],
            log['details'],
            log['log_type'],
            log.get('user_id', '')
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=system_logs.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output