"""
Fine model for tracking user fines and penalties.

This module provides detailed tracking of all fines including
late returns, damaged books, and lost materials with payment status.
"""
from datetime import datetime
from typing import Optional, List, Tuple
import uuid
from models.database import get_db


class Fine:
    """Represents a user fine record.
    
    Attributes:
        id (str): Unique fine identifier.
        user_id (str): ID of user who received the fine.
        borrow_id (str): Related borrow transaction (optional).
        fine_type (str): Type ('late_return', 'damaged_book', 'lost_book').
        description (str): Detailed description of fine.
        fine_amount (float): Fine amount in VND.
        payment_status (str): Payment status ('unpaid', 'paid', 'waived').
        fine_date (str): When fine was created.
        payment_date (str): When fine was paid (optional).
    """

    def __init__(self, id: str = None, fine_id: str = None, user_id: str = None,
                 borrow_id: Optional[str] = None,
                 fine_type: str = None, violation_type: str = None,
                 description: str = '', fine_amount: float = 0,
                 payment_status: str = 'unpaid', fine_date: str = None,
                 violation_date: str = None, payment_date: Optional[str] = None,
                 **kwargs) -> None:
        """Initialize Fine instance.

        Supports both old field names (violation_type, violation_date)
        and new field names (fine_type, fine_date) for DB compatibility.
        """
        self.id = id or fine_id
        self.user_id = user_id
        self.borrow_id = borrow_id
        # Support both old and new field names for backward compatibility
        self.fine_type = fine_type or violation_type or 'unknown'
        self.description = description
        self.fine_amount = float(fine_amount) if fine_amount else 0
        self.payment_status = payment_status
        self.fine_date = fine_date or violation_date
        self.payment_date = payment_date
    
    @staticmethod
    def create(user_id: str, fine_type: str, description: str,
               fine_amount: float, borrow_id: Optional[str] = None) -> 'Fine':
        """Create a new fine record.
        
        Args:
            user_id: ID of user who received fine.
            fine_type: Type of fine ('late_return', 'damaged_book', 'lost_book').
            description: Detailed description.
            fine_amount: Fine amount to charge.
            borrow_id: Related borrow ID (optional).
            
        Returns:
            New Fine instance.
        """
        db = get_db()
        
        fine_id = str(uuid.uuid4())
        fine_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Use old column names for DB compatibility
        db.execute('''
            INSERT INTO violations_history 
            (id, user_id, borrow_id, violation_type, description,
             fine_amount, payment_status, violation_date, payment_date)
            VALUES (?, ?, ?, ?, ?, ?, 'unpaid', ?, NULL)
        ''', (fine_id, user_id, borrow_id, fine_type, description,
              fine_amount, fine_date))
        db.commit()
        
        # Log fine
        from models.system_log import SystemLog
        from models.user import User
        user = User.get_by_id(user_id)
        if user:
            SystemLog.add(
                'Fine Recorded',
                f'{user.name}: {fine_type} - Fine: {fine_amount:,.0f} VND',
                'warning',
                user_id
            )
        
        return Fine.get_by_id(fine_id)
    
    @staticmethod
    def get_by_id(fine_id: str) -> Optional['Fine']:
        """Get fine by ID."""
        db = get_db()
        row = db.execute(
            'SELECT * FROM violations_history WHERE id = ?',
            (fine_id,)
        ).fetchone()
        
        if row:
            return Fine(**dict(row))
        return None
    
    @staticmethod
    def get_user_fines(user_id: str, 
                       payment_status: Optional[str] = None) -> List['Fine']:
        """Get all fines for a user.
        
        Args:
            user_id: User ID.
            payment_status: Filter by payment status (optional).
            
        Returns:
            List of Fine objects.
        """
        db = get_db()
        
        if payment_status:
            rows = db.execute('''
                SELECT * FROM violations_history
                WHERE user_id = ? AND payment_status = ?
                ORDER BY violation_date DESC
            ''', (user_id, payment_status)).fetchall()
        else:
            rows = db.execute('''
                SELECT * FROM violations_history
                WHERE user_id = ?
                ORDER BY violation_date DESC
            ''', (user_id,)).fetchall()
        
        return [Fine(**dict(row)) for row in rows]
    
    @staticmethod
    def get_unpaid_total(user_id: str) -> float:
        """Get total unpaid fines for a user.
        
        Args:
            user_id: User ID.
            
        Returns:
            Total unpaid amount.
        """
        db = get_db()
        result = db.execute('''
            SELECT SUM(fine_amount) as total
            FROM violations_history
            WHERE user_id = ? AND payment_status = 'unpaid'
        ''', (user_id,)).fetchone()
        
        return result['total'] if result['total'] else 0.0
    
    def mark_paid(self) -> Tuple[bool, str]:
        """Mark fine as paid.
        
        Returns:
            Tuple of (success, message).
        """
        if self.payment_status == 'paid':
            return False, "Fine already marked as paid"
        
        db = get_db()
        payment_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.payment_status = 'paid'
        self.payment_date = payment_date
        
        db.execute('''
            UPDATE violations_history
            SET payment_status = ?, payment_date = ?
            WHERE id = ?
        ''', ('paid', payment_date, self.id))
        db.commit()
        
        # Log payment
        from models.system_log import SystemLog
        from models.user import User
        user = User.get_by_id(self.user_id)
        if user:
            SystemLog.add(
                'Fine Payment',
                f'{user.name} paid fine: {self.fine_amount:,.0f} VND ({self.fine_type})',
                'admin',
                self.user_id
            )
        
        return True, "Fine marked as paid"
    
    def mark_waived(self, reason: str = "") -> Tuple[bool, str]:
        """Waive the fine.
        
        Args:
            reason: Reason for waiving the fine.
            
        Returns:
            Tuple of (success, message).
        """
        if self.payment_status == 'waived':
            return False, "Fine already waived"
        
        db = get_db()
        
        self.payment_status = 'waived'
        if reason:
            self.description += f" [WAIVED: {reason}]"
        
        db.execute('''
            UPDATE violations_history
            SET payment_status = ?, description = ?
            WHERE id = ?
        ''', ('waived', self.description, self.id))
        db.commit()
        
        # Log waiver
        from models.system_log import SystemLog
        SystemLog.add(
            'Fine Waived',
            f'Waived {self.fine_amount:,.0f} VND fine for user {self.user_id}. Reason: {reason}',
            'admin',
            None
        )
        
        return True, "Fine waived successfully"
    
    def to_dict(self) -> dict:
        """Convert fine to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'borrow_id': self.borrow_id,
            'fine_type': self.fine_type,
            'description': self.description,
            'fine_amount': self.fine_amount,
            'payment_status': self.payment_status,
            'fine_date': self.fine_date,
            'payment_date': self.payment_date
        }


# Backward compatibility alias
Violation = Fine
