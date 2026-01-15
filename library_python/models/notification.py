"""Notification model for user notifications.

This module handles creating, retrieving, and managing
user notifications in the library system.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from models.database import get_db


class Notification:
    """Represents a user notification.

    Attributes:
        id: Unique notification identifier.
        user_id: ID of the user receiving the notification.
        type: Notification type (e.g., 'reminder', 'alert').
        title: Notification title.
        message: Notification message content.
        date: When the notification was created.
        is_read: Whether the notification has been read.
    """

    def __init__(self, id: str, user_id: str, type: str, title: str,
                 message: str, date: str, is_read: int) -> None:
        """Initialize a Notification instance."""
        self.id = id
        self.user_id = user_id
        self.type = type
        self.title = title
        self.message = message
        self.date = date
        self.is_read = bool(is_read)

    @staticmethod
    def create(user_id: str, notification_type: str,
               title: str, message: str) -> Optional['Notification']:
        """Create a new notification."""
        if not title or not message:
            return None
            
        db = get_db()
        notification_id = str(uuid.uuid4())
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        db.execute('''
            INSERT INTO notifications (id, user_id, type, title, message, date, is_read)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        ''', (notification_id, user_id, notification_type, title, message, date))
        db.commit()

        return Notification.get_by_id(notification_id)

    @staticmethod
    def get_by_id(notification_id: str) -> Optional['Notification']:
        """Get notification by ID."""
        db = get_db()
        row = db.execute(
            'SELECT * FROM notifications WHERE id = ?',
            (notification_id,)
        ).fetchone()
        if row:
            return Notification(**dict(row))
        return None

    @staticmethod
    def get_by_user(user_id: str, limit: int = 50) -> List['Notification']:
        """Get notifications for a user."""
        db = get_db()
        rows = db.execute('''
            SELECT * FROM notifications 
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT ?
        ''', (user_id, limit)).fetchall()

        return [Notification(**dict(row)) for row in rows]

    @staticmethod
    def get_unread_count(user_id: str) -> int:
        """Get count of unread notifications."""
        db = get_db()
        row = db.execute('''
            SELECT COUNT(*) as count FROM notifications 
            WHERE user_id = ? AND is_read = 0
        ''', (user_id,)).fetchone()
        return row['count']

    @staticmethod
    def mark_as_read(notification_id: str) -> None:
        """Mark notification as read."""
        db = get_db()
        db.execute(
            'UPDATE notifications SET is_read = 1 WHERE id = ?',
            (notification_id,)
        )
        db.commit()

    @staticmethod
    def mark_all_as_read(user_id: str) -> None:
        """Mark all notifications as read for a user."""
        db = get_db()
        db.execute(
            'UPDATE notifications SET is_read = 1 WHERE user_id = ?',
            (user_id,)
        )
        db.commit()

    @staticmethod
    def delete(notification_id: str) -> None:
        """Delete a notification."""
        db = get_db()
        db.execute('DELETE FROM notifications WHERE id = ?', (notification_id,))
        db.commit()

    @staticmethod
    def send_to_all_users(notification_type: str, title: str,
                          message: str) -> List['Notification']:
        """Send notification to all users."""
        db = get_db()

        # Get all users with role 'user'
        users = db.execute("SELECT id FROM users WHERE role = 'user'").fetchall()

        notifications = []
        for user in users:
            notif = Notification.create(user['id'], notification_type, title, message)
            notifications.append(notif)

        return notifications

    @staticmethod
    def send_to_specific_users(user_ids: List[str], notification_type: str,
                               title: str, message: str) -> List['Notification']:
        """Send notification to specific users."""
        notifications = []
        for user_id in user_ids:
            notif = Notification.create(user_id, notification_type, title, message)
            notifications.append(notif)

        return notifications

    def to_dict(self) -> dict:
        """Convert notification to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'date': self.date,
            'is_read': self.is_read
        }