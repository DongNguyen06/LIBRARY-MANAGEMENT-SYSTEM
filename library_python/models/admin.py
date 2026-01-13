"""Admin model module.

This module defines the Admin class for system administrators.
Admin inherits from Staff (and thus User) and has full system access.
"""
from typing import List, Dict
from models.database import get_db
from models.staff import Staff


class Admin(Staff):
    """Represents a system administrator.
    
    Admins have full system access including:
    - All Staff permissions
    - Manage books (add, edit, delete)
    - Manage users (lock, unlock, change roles)
    - View system logs
    - System configuration
    
    Inherits all attributes and methods from Staff (and User).
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize an Admin instance."""
        super().__init__(*args, **kwargs)
        # Ensure role is set correctly
        self.role = 'admin'
    
    # ==================== ADMIN-SPECIFIC METHODS ====================
    
    def add_book(self, **book_data) -> tuple:
        """Add a new book to the library.
        
        Args:
            **book_data: Book attributes (title, author, etc.).
            
        Returns:
            Tuple of (Book or None, message).
        """
        from models.book import Book
        return Book.create(**book_data)
    
    def update_book(self, book_id: str, **updates) -> tuple:
        """Update an existing book.
        
        Args:
            book_id: ID of the book to update.
            **updates: Fields to update.
            
        Returns:
            Tuple of (success, message).
        """
        from models.book import Book
        book = Book.get_by_id(book_id)
        if not book:
            return False, "Book not found"
        return book.update_fields(**updates)
    
    def delete_book(self, book_id: str) -> tuple:
        """Delete a book from the library.
        
        Args:
            book_id: ID of the book to delete.
            
        Returns:
            Tuple of (success, message).
        """
        from models.book import Book
        book = Book.get_by_id(book_id)
        if not book:
            return False, "Book not found"
        return book.delete()
    
    def lock_user(self, user_id: str) -> tuple:
        """Lock a user account.
        
        Args:
            user_id: ID of the user to lock.
            
        Returns:
            Tuple of (success, message).
        """
        from models.user import User
        user = User.get_by_id(user_id)
        if not user:
            return False, "User not found"
        if user.role == 'admin':
            return False, "Cannot lock admin accounts"
        user.lock()
        
        # Log the action
        from models.system_log import SystemLog
        SystemLog.add('User Locked', f'Admin {self.name} locked user {user.name}', 'warning', self.id)
        
        return True, f"User {user.name} has been locked"
    
    def unlock_user(self, user_id: str) -> tuple:
        """Unlock a user account.
        
        Args:
            user_id: ID of the user to unlock.
            
        Returns:
            Tuple of (success, message).
        """
        from models.user import User
        user = User.get_by_id(user_id)
        if not user:
            return False, "User not found"
        user.unlock()
        
        # Log the action
        from models.system_log import SystemLog
        SystemLog.add('User Unlocked', f'Admin {self.name} unlocked user {user.name}', 'info', self.id)
        
        return True, f"User {user.name} has been unlocked"
    
    def change_user_role(self, user_id: str, new_role: str) -> tuple:
        """Change a user's role.
        
        Args:
            user_id: ID of the user.
            new_role: New role ('user', 'staff', 'admin').
            
        Returns:
            Tuple of (success, message).
        """
        if new_role not in ('user', 'staff', 'admin'):
            return False, "Invalid role"
        
        from models.user import User
        user = User.get_by_id(user_id)
        if not user:
            return False, "User not found"
        
        old_role = user.role
        db = get_db()
        db.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
        db.commit()
        
        # Log the action
        from models.system_log import SystemLog
        SystemLog.add(
            'Role Changed', 
            f'Admin {self.name} changed {user.name} role from {old_role} to {new_role}',
            'info', 
            self.id
        )
        
        return True, f"User role changed to {new_role}"
    
    def get_system_logs(self, limit: int = 100) -> List:
        """Get recent system logs.
        
        Args:
            limit: Maximum number of logs to return.
            
        Returns:
            List of SystemLog instances.
        """
        from models.system_log import SystemLog
        return SystemLog.get_all(limit)
    
    def send_broadcast_notification(self, title: str, message: str) -> tuple:
        """Send notification to all users.
        
        Args:
            title: Notification title.
            message: Notification message.
            
        Returns:
            Tuple of (notifications list or None, message).
        """
        from models.notification import Notification
        return Notification.send_to_all_with_validation(
            'admin_broadcast', title, message, self.role
        )
    
    def get_dashboard_stats(self) -> Dict:
        """Get statistics for admin dashboard.
        
        Returns:
            Dictionary with various statistics.
        """
        from models.user import User
        from models.book import Book
        from models.borrow import Borrow
        
        return {
            'total_users': User.get_total_users(),
            'total_staff': User.get_users_by_role('staff'),
            'total_admins': User.get_users_by_role('admin'),
            'total_books': Book.get_total_count(),
            'pending_borrows': len(Borrow.get_all_pending()),
            'overdue_borrows': len(Borrow.get_overdue_borrows())
        }
    
    @staticmethod
    def get_all_admins() -> List['Admin']:
        """Get all admin users.
        
        Returns:
            List of Admin instances.
        """
        db = get_db()
        rows = db.execute(
            'SELECT id, email, name, phone, birthday, role, member_since, '
            'is_locked, fines, violations, favorites FROM users WHERE role = ?',
            ('admin',)
        ).fetchall()
        return [Admin(**dict(row)) for row in rows]
