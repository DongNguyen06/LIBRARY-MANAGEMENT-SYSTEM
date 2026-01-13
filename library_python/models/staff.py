"""Staff model module.

This module defines the Staff class for library staff members.
Staff inherits from User and has additional permissions for
managing borrow requests and user support.
"""
from typing import List
from models.database import get_db
from models.user import User


class Staff(User):
    """Represents a library staff member.
    
    Staff members have additional permissions:
    - Approve/reject borrow requests
    - Process book returns
    - Send notifications to users
    - Handle chat support
    - View pending requests
    
    Inherits all attributes and methods from User.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize a Staff instance."""
        super().__init__(*args, **kwargs)
        # Ensure role is set correctly
        if self.role not in ('staff', 'admin'):
            self.role = 'staff'
    
    # ==================== STAFF-SPECIFIC METHODS ====================
    
    def get_pending_borrows(self) -> List:
        """Get all pending borrow requests for processing.
        
        Returns:
            List of pending Borrow instances.
        """
        from models.borrow import Borrow
        return Borrow.get_all_pending()
    
    def approve_borrow(self, borrow_id: str) -> tuple:
        """Approve a borrow pickup request.
        
        Args:
            borrow_id: ID of the borrow to approve.
            
        Returns:
            Tuple of (success, message).
        """
        from models.borrow import Borrow
        borrow = Borrow.get_by_id(borrow_id)
        if not borrow:
            return False, "Borrow request not found"
        return borrow.approve_pickup()
    
    def process_return(self, borrow_id: str, condition: str = 'good') -> tuple:
        """Process a book return.
        
        Args:
            borrow_id: ID of the borrow to return.
            condition: Book condition ('good', 'minor_damage', 'major_damage', 'lost').
            
        Returns:
            Tuple of (success, message).
        """
        from models.borrow import Borrow
        borrow = Borrow.get_by_id(borrow_id)
        if not borrow:
            return False, "Borrow record not found"
        return borrow.return_book(condition)
    
    def send_notification_to_user(self, user_id: str, title: str, message: str) -> tuple:
        """Send a notification to a specific user.
        
        Args:
            user_id: ID of the user to notify.
            title: Notification title.
            message: Notification message.
            
        Returns:
            Tuple of (Notification or None, message).
        """
        from models.notification import Notification
        return Notification.create_with_validation(
            user_id, 'staff_message', title, message
        )
    
    def get_active_chats(self) -> List:
        """Get list of active chat conversations.
        
        Returns:
            List of recent conversations with details.
        """
        from models.chat_message import ChatMessage
        return ChatMessage.get_recent_conversations_with_details(self.id)
    
    def get_overdue_books(self) -> List:
        """Get all currently overdue books.
        
        Returns:
            List of overdue Borrow instances.
        """
        from models.borrow import Borrow
        return Borrow.get_overdue_borrows()
    
    @staticmethod
    def get_all_staff() -> List['Staff']:
        """Get all staff members.
        
        Returns:
            List of Staff instances.
        """
        db = get_db()
        rows = db.execute(
            'SELECT id, email, name, phone, birthday, role, member_since, '
            'is_locked, fines, violations, favorites FROM users WHERE role = ?',
            ('staff',)
        ).fetchall()
        return [Staff(**dict(row)) for row in rows]
