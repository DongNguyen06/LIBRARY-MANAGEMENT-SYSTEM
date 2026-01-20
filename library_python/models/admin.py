"""Admin model.

Inherits from Staff and adds system config capabilities.
"""
from typing import Dict, Tuple

from models.staff import Staff
from models.system_config import SystemConfig
from models.system_log import SystemLog
from models.database import get_db  # <--- Thêm import này để tính toán fines

class Admin(Staff):

    def get_book_interaction_status(self, book_id: str, book_obj=None) -> dict:
        """Override to enforce read-only review access for Admin.
        
        Args:
            book_id: Book identifier.
            book_obj: Optional Book object.
        
        Returns:
            Dictionary with interaction flags (can_review always False).
        """
        status = super().get_book_interaction_status(book_id, book_obj)
        # CRITICAL: Admin cannot review (read-only)
        status['can_review'] = False
        status['user_review'] = None  # Don't show review form
        return status

    def save_system_config(self, config_data: Dict) -> Tuple[bool, str]:
        """Save system configuration.

        Args:
            config_data: Dictionary containing config values.

        Returns:
            Tuple of (success, message).
        """
        SystemConfig.update(config_data)

        # Create detailed log
        details = ", ".join([f"{k}: {v}" for k, v in config_data.items()])
        SystemLog.add(
            'Config Update',
            f'Admin {self.name} updated config: {details}',
            'admin',
            self.id
        )

        return True, "Configuration saved successfully"

    def clear_system_logs(self, days: int) -> Tuple[bool, str]:
        """Clear old system logs.

        Args:
            days: Number of days to keep (delete older than this).

        Returns:
            Tuple of (success, message).
        """
        try:
            SystemLog.clear_old_logs(days)
            SystemLog.add(
                'Clear Logs',
                f'Admin {self.name} cleared logs older than {days} days',
                'admin',
                self.id
            )
            return True, f"Deleted logs older than {days} days"
        except Exception as e:
            return False, str(e)

    def get_stats(self) -> Dict[str, any]:
        """Get dashboard statistics for admin.
        
        Updated to be compatible with Staff Dashboard as well.
        """
        from models.book import Book
        from models.borrow import Borrow
        from models.user import User
        
        # Calculate total debt (fines) - Logic copied from Staff model
        db = get_db()
        total_debt_row = db.execute(
            'SELECT SUM(fines) as total FROM users'
        ).fetchone()
        total_debt = total_debt_row['total'] or 0.0

        # Get core metrics
        active_borrows = Borrow.get_active_borrows_count()
        overdue_count = Borrow.get_overdue_count()
        total_users = User.get_total_users()
        total_books = Book.get_total_count()

        stats = {
            # --- Admin Dashboard Keys ---
            'total_books': total_books,
            'total_users': total_users,
            'active_borrows': active_borrows,
            'overdue_count': overdue_count,
            'total_staff': User.get_users_by_role('staff'),
            'revenue': 0,  # Placeholder

            # --- Staff Dashboard Compatibility Keys (Aliases) ---
            # Template staff/dashboard.html expects these specific keys:
            'fines': total_debt,         # Fixes: 'dict object' has no attribute 'fines'
            'borrowed': active_borrows,  # Alias for active_borrows
            'overdue': overdue_count,    # Alias for overdue_count
            'members': total_users,      # Alias for total_users
            'unread_messages': 0
        }

        return stats