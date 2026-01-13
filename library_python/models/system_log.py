"""System log model for tracking system activities.

This module provides logging functionality for tracking
all system activities, user actions, and errors.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from models.database import get_db


class SystemLog:
    """System activity log for tracking all system events.

    This class provides static methods for adding and retrieving
    system log entries. No instances are created.
    """

    @staticmethod
    def add(action: str, details: str, log_type: str = 'info',
            user_id: Optional[str] = None) -> str:
        """Add a new system log entry.

        Args:
            action: The action being logged.
            details: Detailed description of the action.
            log_type: Log level ('info', 'warning', 'error', 'admin').
            user_id: ID of user who performed the action (optional).

        Returns:
            The ID of the created log entry.
        """
        db = get_db()
        log_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        db.execute('''
            INSERT INTO system_logs (id, timestamp, action, details, log_type, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (log_id, timestamp, action, details, log_type, user_id))
        db.commit()
        return log_id

    @staticmethod
    def get_recent(limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent system logs.

        Args:
            limit: Maximum number of logs to retrieve.

        Returns:
            List of log entries as dictionaries.
        """
        db = get_db()
        logs = db.execute('''
            SELECT * FROM system_logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,)).fetchall()

        return [dict(log) for log in logs]

    @staticmethod
    def clear_old_logs(days: int = 30) -> bool:
        """Clear logs older than specified days.

        Args:
            days: Number of days to keep logs.

        Returns:
            True if operation completed successfully.
        """
        db = get_db()
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

        db.execute('DELETE FROM system_logs WHERE timestamp < ?', (cutoff_str,))
        db.commit()
        return True
