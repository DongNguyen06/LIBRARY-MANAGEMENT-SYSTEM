"""Fine model module.
Handles fine logic and violation history tracking.
"""
import uuid
from datetime import datetime


class Fine:
    def __init__(self, id, user_id, amount, reason, date, status='unpaid'):
        self.id = id
        self.user_id = user_id
        self.amount = amount
        self.reason = reason
        self.date = date
        self.status = status

    @staticmethod
    def create(user_id, amount, reason, borrow_id=None):
        """Create violation record and track fine amount.
        
        ✅ FIXED: Properly handles violations_history table creation
        
        Args:
            user_id: User who incurred the fine
            amount: Fine amount (VND)
            reason: Reason for fine (late fee, damage, etc.)
            borrow_id: Associated borrow transaction ID
            
        Returns:
            fine_id if successful, None otherwise
        """
        from models.database import get_db
        
        if amount <= 0:
            return None
            
        db = get_db()
        fine_id = str(uuid.uuid4())
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Insert into violations_history with payment_status = 'unpaid'
            # This tracks the violation record and fine for future reference
            db.execute('''
                INSERT INTO violations_history 
                (id, user_id, borrow_id, violation_type, description, fine_amount, 
                 payment_status, violation_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fine_id, user_id, borrow_id, 'fine', reason, amount, 'unpaid', date))
            
            # Add to user's fines balance
            db.execute(
                'UPDATE users SET fines = fines + ? WHERE id = ?', 
                (amount, user_id)
            )
            
            db.commit()
            
            return fine_id
        except Exception as e:
            db.rollback()
            print(f"Error creating fine: {e}")
            return None

    @staticmethod
    def get_user_unpaid_fines(user_id):
        """Get all unpaid fines for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of unpaid violation records
        """
        from models.database import get_db
        
        db = get_db()
        rows = db.execute('''
            SELECT * FROM violations_history 
            WHERE user_id = ? AND payment_status = 'unpaid'
            ORDER BY violation_date DESC
        ''', (user_id,)).fetchall()
        
        return [dict(row) for row in rows] if rows else []