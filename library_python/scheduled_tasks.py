from config.config import Config  # Đảm bảo đã import Config
"""
Scheduled background tasks for the library system.

Tasks include:
- Auto-cancelling expired pickup requests (every hour)
- Sending due date reminders (daily)
- ✅ FIXED: Notifying users about cancelled pickups
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from models.borrow import Borrow
from models.notification import Notification
from models.system_log import SystemLog
from models.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def auto_cancel_expired_pickups():
    """Scheduled task: Cancel pickup requests exceeding 48-hour deadline.
    
    ✅ FIXED: Now sends notification to user when pickup is auto-cancelled
    
    Runs every hour to check for expired pending_pickup borrows.
    """
    try:
        # 1. Get list of expired pickups BEFORE cancelling
        expired_list = Borrow.get_expired_pickups_details(hours=Config.PENDING_PICKUP_HOURS)
        
        # 2. Send notifications to affected users
        for row in expired_list:
            user_id = row['user_id']
            book_title = row['title']
            
            # Send notification
            Notification.create(
                user_id=user_id,
                notification_type='alert',
                title='Reservation Cancelled - Pickup Expired',
                message=f'Your reservation for "{book_title}" has been automatically cancelled '
                        f'because it was not picked up within {Config.PENDING_PICKUP_HOURS} hours. '
                        f'You can reserve it again if needed.'
            )

        # 3. Then perform the actual cancellation
        cancelled_count = Borrow.auto_cancel_expired_pickups()
        
        if cancelled_count > 0:
            logger.info(f"Auto-cancelled {cancelled_count} expired pickup requests and notified users.")
            SystemLog.add(
                'Scheduled Task: Auto-cancel Expired Pickups',
                f'Successfully cancelled {cancelled_count} expired pickup(s) and sent {cancelled_count} notification(s)',
                'system',
                None
            )
    except Exception as e:
        logger.error(f"Error in auto_cancel_expired_pickups: {e}")
        SystemLog.add(
            'Scheduled Task Error',
            f'Failed to auto-cancel pickups: {str(e)}',
            'error',
            None
        )


def send_due_date_reminders():
    """Scheduled task: Send reminders for books due within 3 days.
    
    Runs daily at 9:00 AM to notify users about upcoming due dates.
    """
    try:
        db = get_db()
        today = datetime.now()
        three_days_later = (today + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        
        # Find books due within 3 days
        upcoming_due = db.execute('''
            SELECT b.id, b.user_id, b.book_id, b.due_date, u.name as user_name, 
                   bk.title as book_title
            FROM borrows b
            JOIN users u ON b.user_id = u.id
            JOIN books bk ON b.book_id = bk.id
            WHERE b.status = 'borrowed' AND b.due_date <= ? AND b.due_date > ?
        ''', (three_days_later, today.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
        
        reminder_count = 0
        for row in upcoming_due:
            # Create notification
            due_date = datetime.strptime(row['due_date'], '%Y-%m-%d %H:%M:%S')
            days_remaining = (due_date - today).days
            
            message = f'Reminder: "{row["book_title"]}" is due in {days_remaining} day(s) on {due_date.strftime("%Y-%m-%d")}. Please return or renew it.'
            
            Notification.create(
                user_id=row['user_id'],
                notification_type='reminder',
                title='Book Due Date Reminder',
                message=message
            )
            reminder_count += 1
        
        if reminder_count > 0:
            logger.info(f"Sent {reminder_count} due date reminder(s)")
            SystemLog.add(
                'Scheduled Task: Due Date Reminders',
                f'Successfully sent {reminder_count} reminder(s)',
                'system',
                None
            )
    except Exception as e:
        logger.error(f"Error in send_due_date_reminders: {e}")
        SystemLog.add(
            'Scheduled Task Error',
            f'Failed to send reminders: {str(e)}',
            'error',
            None
        )


def send_overdue_notifications():
    """Scheduled task: Send notifications for overdue books.
    
    Runs daily at 10:00 AM to notify users about overdue books.
    """
    try:
        db = get_db()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Find overdue books
        overdue_borrows = db.execute('''
            SELECT b.id, b.user_id, b.book_id, b.due_date, u.name as user_name,
                   bk.title as book_title
            FROM borrows b
            JOIN users u ON b.user_id = u.id
            JOIN books bk ON b.book_id = bk.id
            WHERE b.status = 'borrowed' AND b.due_date < ?
        ''', (now,)).fetchall()
        
        notification_count = 0
        for row in overdue_borrows:
            due_date = datetime.strptime(row['due_date'], '%Y-%m-%d %H:%M:%S')
            days_overdue = (datetime.now() - due_date).days
            
            message = f'Overdue Alert: "{row["book_title"]}" is {days_overdue} day(s) overdue. Late fees are accumulating. Please return immediately.'
            
            Notification.create(
                user_id=row['user_id'],
                notification_type='alert',
                title='Overdue Book Alert',
                message=message
            )
            notification_count += 1
        
        if notification_count > 0:
            logger.info(f"Sent {notification_count} overdue notification(s)")
            SystemLog.add(
                'Scheduled Task: Overdue Notifications',
                f'Successfully sent {notification_count} notification(s)',
                'system',
                None
            )
    except Exception as e:
        logger.error(f"Error in send_overdue_notifications: {e}")
        SystemLog.add(
            'Scheduled Task Error',
            f'Failed to send overdue notifications: {str(e)}',
            'error',
            None
        )


# Initialize scheduler
scheduler = BackgroundScheduler()

# Schedule tasks
scheduler.add_job(
    func=auto_cancel_expired_pickups,
    trigger='interval',
    hours=1,
    id='auto_cancel_expired_pickups',
    name='Auto-cancel expired pickup requests',
    replace_existing=True
)

scheduler.add_job(
    func=send_due_date_reminders,
    trigger='cron',
    hour=9,
    minute=0,
    id='send_due_date_reminders',
    name='Send due date reminders',
    replace_existing=True
)

scheduler.add_job(
    func=send_overdue_notifications,
    trigger='cron',
    hour=10,
    minute=0,
    id='send_overdue_notifications',
    name='Send overdue notifications',
    replace_existing=True
)


def start_scheduler(app):
    """Start the background scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduled tasks started successfully")
        
        # Use app context for database operations
        with app.app_context():
            try:
                SystemLog.add(
                    'System Startup',
                    'Background task scheduler started',
                    'system',
                    None
                )
            except Exception as e:
                logger.error(f"Error logging scheduler startup: {e}")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduled tasks shut down")