"""
Borrow model with improved fine calculation and business rules.

Updated to implement:
1. Proper fine calculation (grace period + hourly/daily rates)
2. 48-hour pending pickup logic
3. Damage/loss penalties
4. Reservation checking for renewals
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from models.database import get_db
from models.book import Book
from config.config import Config


class Borrow:
    def __init__(self, id, user_id, book_id, borrow_date, due_date, return_date,
                 status, renewed_count, pending_until=None, condition=None, 
                 damage_fee=0.0, late_fee=0.0):
        self.id = id
        self.user_id = user_id
        self.book_id = book_id
        self.borrow_date = borrow_date
        self.due_date = due_date
        self.return_date = return_date
        self.status = status
        self.renewed_count = int(renewed_count)
        self.pending_until = pending_until
        self.condition = condition
        self.damage_fee = float(damage_fee) if damage_fee else 0.0
        self.late_fee = float(late_fee) if late_fee else 0.0
    
    @staticmethod
    def calculate_late_fee(due_date: datetime, return_date: datetime) -> float:
        """Calculate late fee with grace period and tiered rates.
        
        SRS Requirements:
        - Grace Period: First 30 minutes are FREE
        - Short-term delay (< 24 hours after grace): 2,000 VND/hour
        - Long-term delay (>= 24 hours after grace): 10,000 VND/day
        
        Args:
            due_date: When book was due.
            return_date: When book was actually returned.
            
        Returns:
            Late fee amount.
        """
        # No fee if returned on time
        if return_date <= due_date:
            return 0.0
        
        # Calculate delay
        delay_timedelta = return_date - due_date
        total_minutes = delay_timedelta.total_seconds() / 60
        
        # Grace period settings
        grace_minutes = Config.GRACE_PERIOD_MINUTES
        hourly_rate = Config.LATE_FEE_HOURLY
        daily_rate = Config.LATE_FEE_DAILY
        
        # Within grace period -> No charge
        if total_minutes <= grace_minutes:
            return 0.0
        
        # Calculate effective delay after grace period
        effective_minutes = total_minutes - grace_minutes
        effective_hours = effective_minutes / 60
        effective_days = effective_hours / 24
        
        # Short-term delay: < 24 hours -> Charge by hour
        if effective_hours < 24:
            # Round up to next hour
            hours_to_charge = int(effective_hours) + (1 if effective_hours % 1 > 0 else 0)
            return hours_to_charge * hourly_rate
        
        # Long-term delay: >= 24 hours -> Charge by day
        else:
            # Round up to next day
            days_to_charge = int(effective_days) + (1 if effective_days % 1 > 0 else 0)
            return days_to_charge * daily_rate
    
    @staticmethod
    def calculate_damage_fee(condition: str, book_value: float) -> float:
        """Calculate damage or loss fee based on condition.
        
        SRS Requirements:
        - Minor Damage (Level 1): 20% of book value
        - Major Damage (Level 2): 100% of book value + 15,000 VND processing
        - Lost Material (Level 3): 100% of book value + 20,000 VND re-stocking
        
        Args:
            condition: Book condition ('good', 'minor_damage', 'major_damage', 'lost').
            book_value: Original value of the book.
            
        Returns:
            Damage/loss fee amount.
        """
        if condition == 'good':
            return 0.0
        elif condition == 'minor_damage':
            return book_value * 0.20
        elif condition == 'major_damage':
            return book_value + 15000.0
        elif condition == 'lost':
            return book_value + 20000.0
        else:
            return 0.0

    @staticmethod
    def get_by_id(borrow_id):
        """Get borrow by ID"""
        db = get_db()
        row = db.execute('SELECT * FROM borrows WHERE id = ?', (borrow_id,)).fetchone()
        if row:
            return Borrow(**dict(row))
        return None
    
    @staticmethod
    def get_user_borrows(user_id, status=None):
        """Get all borrows for a user"""
        db = get_db()
        
        if status:
            rows = db.execute(
                'SELECT * FROM borrows WHERE user_id = ? AND status = ? ORDER BY borrow_date DESC',
                (user_id, status)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM borrows WHERE user_id = ? ORDER BY borrow_date DESC',
                (user_id,)
            ).fetchall()
        
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def get_active_borrows(user_id):
        """Get active borrows (pending_pickup or borrowed).
        
        Status flow:
        - pending_pickup: User requested, waiting for pickup (book is reserved)
        - borrowed: User has picked up the book
        
        Note: Old 'waiting' status is deprecated and NOT included here.
        """
        db = get_db()
        rows = db.execute(
            "SELECT * FROM borrows WHERE user_id = ? AND status IN ('borrowed', 'pending_pickup') ORDER BY borrow_date DESC",
            (user_id,)
        ).fetchall()
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def get_overdue_borrows(user_id=None):
        """Get overdue borrows"""
        db = get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        
        if user_id:
            rows = db.execute(
                "SELECT * FROM borrows WHERE user_id = ? AND status = 'borrowed' AND due_date < ? ORDER BY due_date ASC",
                (user_id, today)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM borrows WHERE status = 'borrowed' AND due_date < ? ORDER BY due_date ASC",
                (today,)
            ).fetchall()
        
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def get_upcoming_due(user_id, days=3):
        """Get borrows due within specified days"""
        db = get_db()
        today = datetime.now()
        future_date = (today + timedelta(days=days)).strftime('%Y-%m-%d')
        today_str = today.strftime('%Y-%m-%d')
        
        rows = db.execute(
            "SELECT * FROM borrows WHERE user_id = ? AND status = 'borrowed' AND due_date BETWEEN ? AND ? ORDER BY due_date ASC",
            (user_id, today_str, future_date)
        ).fetchall()
        
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def get_all_pending():
        """Get all pending borrow requests (pending_pickup status).
        
        Note: Old 'waiting' status is deprecated. New flow uses 'pending_pickup'.
        """
        db = get_db()
        rows = db.execute(
            "SELECT * FROM borrows WHERE status = 'pending_pickup' ORDER BY borrow_date ASC"
        ).fetchall()
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def get_user_borrows_by_status(status):
        """Get all borrows with a specific status.
        
        Args:
            status: Status to filter by (e.g., 'pending_pickup', 'borrowed', 'returned').
            
        Returns:
            List of Borrow instances.
        """
        db = get_db()
        rows = db.execute(
            "SELECT * FROM borrows WHERE status = ? ORDER BY borrow_date DESC",
            (status,)
        ).fetchall()
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def get_all():
        """Get all borrows"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM borrows ORDER BY borrow_date DESC"
        ).fetchall()
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def create(user_id, book_id):
        """Create new borrow request with DIRECT PENDING status.
        
        NEW FLOW (Senior Dev requirement):
        - User clicks "Borrow Book" → Immediately create pending_pickup record
        - Decrease available_copies RIGHT AWAY to reserve the book
        - Set pending_until = now + 48 hours
        - Staff approves pickup later when user arrives
        
        Why decrease quantity immediately?
        - Prevents race condition: Multiple users borrowing same last copy
        - Reserves the book for this specific user
        - Book is "held" but not yet "borrowed" until pickup confirmation
        
        Args:
            user_id: ID of user requesting to borrow
            book_id: ID of book to borrow
            
        Returns:
            Tuple of (Borrow instance or None, message string)
        """
        import uuid
        db = get_db()
        
        # Validation 1: Check book availability
        book = Book.get_by_id(book_id)
        if not book:
            return None, "Book not found"
        if book.available_copies <= 0:
            return None, "Book is not available. Please reserve it instead."
        
        # Validation 2: Check user borrow limit (max 5 books)
        active_borrows = Borrow.get_active_borrows(user_id)
        if len(active_borrows) >= Config.MAX_BORROW_LIMIT:
            return None, f"You have reached the maximum borrow limit of {Config.MAX_BORROW_LIMIT} books"
        
        # Validation 3: Check if user already borrowed/requested this book
        for borrow in active_borrows:
            if borrow.book_id == book_id:
                return None, "You have already borrowed or requested this book"
        
        # Validation 4: Check for unpaid fines
        from models.user import User
        user = User.get_by_id(user_id)
        if user and user.fines > 0:
            return None, f"Please pay your outstanding fine of {user.fines:,.0f} VND before borrowing"
        
        # Generate IDs and timestamps
        borrow_id = str(uuid.uuid4())
        now = datetime.now()
        borrow_date = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # Set pending_until = now + 48 hours (user must pickup within this time)
        pending_until = (now + timedelta(hours=Config.PENDING_PICKUP_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
        
        # Note: due_date will be set later when staff approves pickup
        # For now, we estimate it as 7 days from now (will be recalculated on approval)
        estimated_due_date = (now + timedelta(days=Config.BORROW_DURATION_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Create borrow record with status='pending_pickup'
            db.execute('''
                INSERT INTO borrows (id, user_id, book_id, borrow_date, due_date, 
                                   return_date, status, renewed_count, pending_until,
                                   condition, damage_fee, late_fee)
                VALUES (?, ?, ?, ?, ?, NULL, 'pending_pickup', 0, ?, NULL, 0, 0)
            ''', (borrow_id, user_id, book_id, borrow_date, estimated_due_date, pending_until))
            
            # CRITICAL: Decrease available_copies immediately to reserve the book
            # This prevents other users from borrowing the same copy
            book.update_available_copies(-1)
            
            # Increment borrow count for statistics
            book.increment_borrow_count()
            
            db.commit()
            
            # Log the action
            from models.system_log import SystemLog
            if user:
                SystemLog.add(
                    'Book Hold Created',
                    f'{user.name} created pending pickup for "{book.title}" (Must pickup by {pending_until})',
                    'info',
                    user_id
                )
            
            return Borrow.get_by_id(borrow_id), f"Book reserved! Please pick it up within 48 hours (by {pending_until})"
            
        except Exception as e:
            db.rollback()
            print(f"Error creating borrow: {e}")
            return None, f"Failed to create borrow request: {str(e)}"
    
    def approve(self):
        """Approve borrow request (staff/admin)"""
        if self.status != 'waiting':
            return False, "Only waiting requests can be approved"
        
        self.status = 'borrowed'
        db = get_db()
        db.execute('UPDATE borrows SET status = ? WHERE id = ?', ('borrowed', self.id))
        db.commit()
        
        return True, "Borrow request approved"
    
    def approve_pickup(self):
        """Approve and complete book pickup by user.
        
        NEW FLOW (Senior Dev requirement):
        - Staff calls this when user arrives to pick up the book
        - Status changes from 'pending_pickup' → 'borrowed'
        - due_date is SET HERE (now + 7 days) NOT at creation time
        - This ensures accurate 7-day borrow period from actual pickup
        
        Returns:
            Tuple of (success, message).
        """
        if self.status != 'pending_pickup':
            return False, "Only pending pickup requests can be approved"
        
        # Check if pickup deadline has passed
        if self.pending_until:
            deadline = datetime.strptime(self.pending_until, '%Y-%m-%d %H:%M:%S')
            if datetime.now() > deadline:
                self.cancel()
                return False, "Pickup deadline has passed. Request has been cancelled."
        
        db = get_db()
        now = datetime.now()
        
        # Update status to 'borrowed'
        self.status = 'borrowed'
        
        # CRITICAL: Set due_date = NOW + 7 days (actual borrow period starts now)
        # This is different from estimated due_date set during creation
        self.due_date = (now + timedelta(days=Config.BORROW_DURATION_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        
        db.execute('''
            UPDATE borrows 
            SET status = ?, due_date = ? 
            WHERE id = ?
        ''', ('borrowed', self.due_date, self.id))
        db.commit()
        
        # Log pickup confirmation
        from models.system_log import SystemLog
        from models.user import User
        user = User.get_by_id(self.user_id)
        book = Book.get_by_id(self.book_id)
        if user and book:
            SystemLog.add(
                'Book Pickup Confirmed',
                f'{user.name} picked up "{book.title}" (Due: {self.due_date})',
                'info',
                self.user_id
            )
        
        return True, f"Book pickup confirmed! Please return by {self.due_date}"
        from models.system_log import SystemLog
        from models.user import User
        user = User.get_by_id(self.user_id)
        book = Book.get_by_id(self.book_id)
        if user and book:
            SystemLog.add(
                'Book Pickup Completed',
                f'{user.name} picked up "{book.title}"',
                'info',
                self.user_id
            )
        
        return True, "Book pickup approved. Status changed to borrowed."

    def return_book(self, condition='good', book_value=0.0):
        """Return borrowed book with condition assessment and proper fee calculation.
        
        Args:
            condition: Book condition ('good', 'minor_damage', 'major_damage', 'lost').
            book_value: Original value of book for damage fee calculation.
            
        Returns:
            Tuple of (success, message).
        """
        if self.status != 'borrowed':
            return False, "Only borrowed books can be returned"
        
        from models.user import User
        from models.reservation import Reservation
        from models.system_log import SystemLog
        
        db = get_db()
        return_timestamp = datetime.now()
        self.return_date = return_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        self.status = 'returned'
        self.condition = condition
        
        # Calculate late fee with grace period
        due_timestamp = datetime.strptime(self.due_date, '%Y-%m-%d %H:%M:%S')
        self.late_fee = self.calculate_late_fee(due_timestamp, return_timestamp)
        
        # Calculate damage fee
        self.damage_fee = self.calculate_damage_fee(condition, book_value)
        
        # Update database
        db.execute('''
            UPDATE borrows 
            SET status = ?, return_date = ?, condition = ?, 
                late_fee = ?, damage_fee = ?
            WHERE id = ?
        ''', (self.status, self.return_date, self.condition,
              self.late_fee, self.damage_fee, self.id))
        
        # Return book to inventory
        book = Book.get_by_id(self.book_id)
        if book:
            book.update_available_copies(1)
        
        # Apply fines to user account
        total_fine = self.late_fee + self.damage_fee
        if total_fine > 0:
            user = User.get_by_id(self.user_id)
            if user:
                user.add_fine(total_fine)
                user.add_violation()
        
        db.commit()
        
        # Check for reservations and notify next in queue
        if Reservation.has_active_reservations(self.book_id):
            next_reservation = Reservation.get_next_in_queue(self.book_id)
            if next_reservation:
                next_reservation.mark_ready(hold_hours=48)
        
        # Log return
        user = User.get_by_id(self.user_id)
        if user and book:
            details = f'{user.name} returned "{book.title}" (Condition: {condition}'
            if total_fine > 0:
                details += f', Total Fine: {total_fine:,.0f} VND'
            details += ')'
            SystemLog.add('Book Returned', details, 'info', self.user_id)
        
        return True, f"Book returned. Late fee: {self.late_fee:,.0f} VND, Damage fee: {self.damage_fee:,.0f} VND"
    
    def renew(self, extension_days=7):
        """Renew borrowed book with proper business rules.
        
        SRS Requirements:
        - Extension days: 7 days (not 14)
        - Only allowed once (renewed_count < 1)
        - Not allowed if someone has reserved this book
        - Not allowed if book is overdue
        
        Args:
            extension_days: Number of days to extend (default 7).
            
        Returns:
            Tuple of (success, message).
        """
        if self.status != 'borrowed':
            return False, "Only borrowed books can be renewed"
        
        # Check renewal limit (max 1 time)
        if self.renewed_count >= 1:
            return False, "Maximum renewal limit (1 time) has been reached"
        
        # Check if book is overdue
        due_timestamp = datetime.strptime(self.due_date, '%Y-%m-%d %H:%M:%S')
        if datetime.now() > due_timestamp:
            return False, "Overdue books cannot be renewed"
        
        # Check if anyone has reserved this book
        from models.reservation import Reservation
        if Reservation.has_active_reservations(self.book_id):
            return False, "Cannot renew: Someone has reserved this book"
        
        # Extend due date by 7 days
        new_due_timestamp = due_timestamp + timedelta(days=extension_days)
        self.due_date = new_due_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        self.renewed_count += 1
        
        db = get_db()
        db.execute('''
            UPDATE borrows SET due_date = ?, renewed_count = ? WHERE id = ?
        ''', (self.due_date, self.renewed_count, self.id))
        db.commit()
        
        # Log renewal
        from models.system_log import SystemLog
        from models.user import User
        user = User.get_by_id(self.user_id)
        book = Book.get_by_id(self.book_id)
        if user and book:
            SystemLog.add(
                'Book Renewal',
                f'{user.name} renewed "{book.title}" (New due: {self.due_date})',
                'info',
                self.user_id
            )
        
        return True, f"Book renewed successfully. New due date: {self.due_date}"
    
    def cancel(self):
        """Cancel borrow request and restore book availability.
        
        Returns:
            Tuple of (success, message).
        """
        if self.status not in ['pending_pickup']:
            return False, "Only pending pickup requests can be cancelled"
        
        db = get_db()
        self.status = 'cancelled'
        
        # Update status
        db.execute('UPDATE borrows SET status = ? WHERE id = ?', ('cancelled', self.id))
        
        # Return book to available inventory
        book = Book.get_by_id(self.book_id)
        if book:
            book.update_available_copies(1)
        
        db.commit()
        
        # Check for reservations
        from models.reservation import Reservation
        if Reservation.has_active_reservations(self.book_id):
            next_reservation = Reservation.get_next_in_queue(self.book_id)
            if next_reservation:
                next_reservation.mark_ready(hold_hours=48)
        
        return True, "Borrow request cancelled"
    
    @staticmethod
    def auto_cancel_expired_pickups():
        """Auto-cancel all pickup requests that exceeded 48-hour deadline.
        
        This should be run periodically (e.g., every hour) as a background job.
        
        Returns:
            Number of expired pickups cancelled.
        """
        db = get_db()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Find all expired pending pickups
        expired_rows = db.execute('''
            SELECT id FROM borrows
            WHERE status = 'pending_pickup' AND pending_until < ?
        ''', (now,)).fetchall()
        
        cancelled_count = 0
        for row in expired_rows:
            borrow = Borrow.get_by_id(row['id'])
            if borrow:
                success, _ = borrow.cancel()
                if success:
                    cancelled_count += 1
        
        return cancelled_count
        db.execute('DELETE FROM borrows WHERE id = ?', (self.id,))
        db.commit()
        
        return True, "Borrow request cancelled"
    
    def get_book(self):
        """Get the book object"""
        return Book.get_by_id(self.book_id)
    
    def is_overdue(self):
        """Check if borrow is overdue"""
        if self.status != 'borrowed':
            return False
        try:
            # Try parsing with time first
            due_date = datetime.strptime(self.due_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # Fallback to date only format
            due_date = datetime.strptime(self.due_date, '%Y-%m-%d')
        return datetime.now() > due_date
    
    def get_overdue_days(self):
        """Get number of overdue days"""
        if not self.is_overdue():
            return 0
        try:
            # Try parsing with time first
            due_date = datetime.strptime(self.due_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # Fallback to date only format
            due_date = datetime.strptime(self.due_date, '%Y-%m-%d')
        return (datetime.now() - due_date).days
    
    def get_fine_amount(self):
        """Calculate fine amount for overdue"""
        overdue_days = self.get_overdue_days()
        return overdue_days * Config.FINE_PER_DAY
    
    def get_user(self):
        """Get user who borrowed the book"""
        from models.user import User
        return User.get_by_id(self.user_id)
    
    def to_dict(self):
        """Convert borrow to dictionary"""
        book = self.get_book()
        return {
            'id': self.id,
            'user_id': self.user_id,
            'book_id': self.book_id,
            'book': book.to_dict() if book else None,
            'borrow_date': self.borrow_date,
            'due_date': self.due_date,
            'return_date': self.return_date,
            'status': self.status,
            'renewed_count': self.renewed_count,
            'is_overdue': self.is_overdue(),
            'overdue_days': self.get_overdue_days(),
            'fine_amount': self.get_fine_amount()
        }
    
    # ==================== SERVICE METHODS (Merged from BorrowService) ====================
    
    @staticmethod
    def borrow_book(user_id: str, book_id: str) -> tuple:
        """Create borrow request with validation and logging.
        
        Args:
            user_id: ID of user requesting to borrow.
            book_id: ID of book to borrow.
            
        Returns:
            Tuple of (success, message).
        """
        from models.user import User
        from models.system_log import SystemLog
        
        user = User.get_by_id(user_id)
        if not user:
            return False, "User not found"
        
        if user.is_locked:
            return False, "Your account is locked. Please contact the library."
        
        borrow, message = Borrow.create(user_id, book_id)
        if borrow:
            book = Book.get_by_id(book_id)
            if book:
                SystemLog.add(
                    'Book Borrow Request',
                    f'{user.name} requested to borrow "{book.title}"',
                    'info',
                    user_id
                )
            return True, message
        return False, message
    
    @staticmethod
    def return_book_by_user(user_id: str, book_id: str, condition: str = 'good', book_value: float = 0.0) -> tuple:
        """Return borrowed book with condition assessment.
        
        Args:
            user_id: ID of user returning the book.
            book_id: ID of book being returned.
            condition: Book condition.
            book_value: Original value of book for damage fee calculation.
            
        Returns:
            Tuple of (success, message).
        """
        borrows = Borrow.get_active_borrows(user_id)
        for borrow in borrows:
            if borrow.book_id == book_id and borrow.status == 'borrowed':
                return borrow.return_book(condition, book_value)
        
        return False, "No active borrow found for this book"
    
    @staticmethod
    def renew_book_by_user(user_id: str, book_id: str, extension_days: int = 7) -> tuple:
        """Renew borrowed book.
        
        Args:
            user_id: ID of user renewing the book.
            book_id: ID of book to renew.
            extension_days: Number of days to extend.
            
        Returns:
            Tuple of (success, message).
        """
        borrows = Borrow.get_active_borrows(user_id)
        for borrow in borrows:
            if borrow.book_id == book_id and borrow.status == 'borrowed':
                return borrow.renew(extension_days)
        
        return False, "No active borrow found for this book"
    
    @staticmethod
    def cancel_borrow_by_user(user_id: str, book_id: str) -> tuple:
        """Cancel borrow request.
        
        Args:
            user_id: ID of user cancelling the request.
            book_id: ID of book to cancel.
            
        Returns:
            Tuple of (success, message).
        """
        borrows = Borrow.get_user_borrows(user_id, status='pending_pickup')
        for borrow in borrows:
            if borrow.book_id == book_id:
                return borrow.cancel()
        
        return False, "No pending borrow request found for this book"
    
    @staticmethod
    def approve_borrow_by_id(borrow_id: str) -> tuple:
        """Approve borrow request (staff/admin).
        
        Args:
            borrow_id: ID of borrow request to approve.
            
        Returns:
            Tuple of (success, message).
        """
        from models.user import User
        from models.system_log import SystemLog
        
        borrow = Borrow.get_by_id(borrow_id)
        if borrow:
            success, message = borrow.approve()
            if success:
                user = User.get_by_id(borrow.user_id)
                book = Book.get_by_id(borrow.book_id)
                if user and book:
                    SystemLog.add(
                        'Borrow Request Approved',
                        f'Staff approved borrow request: {user.name} for "{book.title}"',
                        'admin',
                        None
                    )
            return success, message
        return False, "Borrow request not found"
    
    @staticmethod
    def get_user_borrowed_books(user_id: str) -> list:
        """Get all borrowed books for a user (including pending_pickup).
        
        Args:
            user_id: ID of user.
            
        Returns:
            List of Borrow instances.
        """
        borrowed = Borrow.get_user_borrows(user_id, status='borrowed')
        pending = Borrow.get_user_borrows(user_id, status='pending_pickup')
        return borrowed + pending
    
    @staticmethod
    def get_user_reserved_books(user_id: str) -> list:
        """Get all reserved books for a user.
        
        Args:
            user_id: ID of user.
            
        Returns:
            List of Reservation instances.
        """
        from models.reservation import Reservation
        return Reservation.get_user_reservations(user_id, status='waiting')
    
    @staticmethod
    def get_user_overdue_books(user_id: str) -> list:
        """Get overdue books for a user.
        
        Args:
            user_id: ID of user.
            
        Returns:
            List of Borrow instances.
        """
        return Borrow.get_overdue_borrows(user_id)
    
    @staticmethod
    def get_upcoming_due_books(user_id: str, days: int = 3) -> list:
        """Get books due within specified days.
        
        Args:
            user_id: ID of user.
            days: Number of days to look ahead.
            
        Returns:
            List of Borrow instances.
        """
        return Borrow.get_upcoming_due(user_id, days)
    
    @staticmethod
    def get_active_borrows_count() -> int:
        """Get total count of active borrows.
        
        Returns:
            Count of active borrows.
        """
        db = get_db()
        row = db.execute(
            "SELECT COUNT(*) as count FROM borrows WHERE status IN ('borrowed', 'waiting')"
        ).fetchone()
        return row['count']
    
    @staticmethod
    def get_overdue_count() -> int:
        """Get total count of overdue books.
        
        Returns:
            Count of overdue borrows.
        """
        db = get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        row = db.execute(
            "SELECT COUNT(*) as count FROM borrows WHERE status = 'borrowed' AND due_date < ?",
            (today,)
        ).fetchone()
        return row['count']
