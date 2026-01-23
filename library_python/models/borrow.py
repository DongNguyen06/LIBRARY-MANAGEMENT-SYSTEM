from datetime import datetime, timedelta
from typing import Optional, Tuple
import uuid
from config.config import Config
from models.book import Book
from models.database import get_db
from models.system_config import SystemConfig

class Borrow:
    
    @staticmethod
    def get_expired_pickups_details(hours=48):
        """Get details of expired pending pickups for notification."""
        db = get_db()
        hold_days = SystemConfig.get_int('reservation_hold_time', 2)
        hold_hours = hold_days * 24
        
        limit_time = (datetime.now() - timedelta(hours=hold_hours)).strftime('%Y-%m-%d %H:%M:%S')
        return db.execute('''
            SELECT b.user_id, bk.title 
            FROM borrows b
            JOIN books bk ON b.book_id = bk.id
            WHERE b.status = 'pending_pickup' AND b.borrow_date <= ?
        ''', (limit_time,)).fetchall()

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
    
    @property
    def is_pending(self) -> bool:
        return self.status == 'pending_pickup'

    @property
    def is_borrowed(self) -> bool:
        return self.status == 'borrowed'

    @property
    def can_be_cancelled(self) -> bool:
        return self.is_pending

    @property
    def is_active(self) -> bool:
        return self.status in ('pending_pickup', 'borrowed')

    @staticmethod
    def calculate_late_fee(due_date: datetime, return_date: datetime) -> float:
        """Calculate late fee with grace period and tiered rates."""
        if return_date <= due_date:
            return 0.0
        
        delay_timedelta = return_date - due_date
        total_minutes = delay_timedelta.total_seconds() / 60
        
        grace_minutes = Config.GRACE_PERIOD_MINUTES
        hourly_rate = Config.LATE_FEE_HOURLY
        daily_rate = SystemConfig.get_float('late_fee_per_day', Config.LATE_FEE_DAILY)
        
        if total_minutes <= grace_minutes:
            return 0.0
        
        effective_minutes = total_minutes - grace_minutes
        effective_hours = effective_minutes / 60
        effective_days = effective_hours / 24
        
        if effective_hours < 24:
            hours_to_charge = int(effective_hours) + (1 if effective_hours % 1 > 0 else 0)
            return hours_to_charge * hourly_rate
        else:
            days_to_charge = int(effective_days) + (1 if effective_days % 1 > 0 else 0)
            return days_to_charge * daily_rate
    
    @staticmethod
    def calculate_damage_fee(condition: str, book_value: float) -> float:
        """Calculate damage or loss fee based on condition."""
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
    def create(user_id, book_id):
        from models.reservation import Reservation
        
        db = get_db()
        
        # ========== VALIDATION 1: Check book existence ==========
        book = Book.get_by_id(book_id)
        if not book:
            return None, "Book not found"
        
        # ========== VALIDATION 2: Check user borrow limit ==========
        active_borrows = Borrow.get_active_borrows(user_id)
        
        # [DYNAMIC] Get Max Limit from DB
        max_limit = SystemConfig.get_int('max_borrowed_books', Config.MAX_BORROW_LIMIT)
        
        if len(active_borrows) >= max_limit:
            return None, f"You have reached the maximum borrow limit of {max_limit} books"
        
        # ========== VALIDATION 3: Check duplicate requests ==========
        for borrow in active_borrows:
            if borrow.book_id == book_id:
                return None, "You have already borrowed or requested this book"
        
        # ========== VALIDATION 4: Check for unpaid fines ==========
        from models.user import User
        user = User.get_by_id(user_id)
        if user and user.fines > 0:
            return None, f"Please pay your outstanding fine of {user.fines:,.0f} VND before borrowing"
        
        # ========== CRITICAL: HIDDEN INVENTORY CHECK ==========
        user_reservation = Reservation.get_user_book_reservation(user_id, book_id)
        has_priority_access = False
        
        if user_reservation and user_reservation.status == 'ready':
            if user_reservation.hold_until:
                hold_deadline = datetime.strptime(
                    user_reservation.hold_until, '%Y-%m-%d %H:%M:%S'
                )
                if datetime.now() <= hold_deadline:
                    has_priority_access = True
                else:
                    user_reservation.cancel()
                    return None, "Your reservation has expired. Please reserve again."
        
        # ========== INVENTORY AVAILABILITY CHECK ==========
        if not has_priority_access:
            if book.available_copies <= 0:
                return None, "Book is not available. Please reserve it instead."
        
        # ========== CREATE BORROW RECORD ==========
        borrow_id = str(uuid.uuid4())
        now = datetime.now()
        borrow_date = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # [DYNAMIC] Get durations from DB
        hold_days = SystemConfig.get_int('reservation_hold_time', 2)
        borrow_days = SystemConfig.get_int('borrow_duration', Config.BORROW_DURATION_DAYS)
        
        pending_until = (now + timedelta(days=hold_days)).strftime('%Y-%m-%d %H:%M:%S')
        estimated_due_date = (now + timedelta(days=borrow_days)).strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            db.execute('''
                INSERT INTO borrows (id, user_id, book_id, borrow_date, due_date, 
                                   return_date, status, renewed_count, pending_until,
                                   condition, damage_fee, late_fee)
                VALUES (?, ?, ?, ?, ?, NULL, 'pending_pickup', 0, ?, NULL, 0, 0)
            ''', (borrow_id, user_id, book_id, borrow_date, estimated_due_date, pending_until))
            
            # ========== CRITICAL: INVENTORY MANAGEMENT ==========
            if has_priority_access:
                user_reservation.complete()
                from models.system_log import SystemLog
                SystemLog.add(
                    'Priority Borrow Created',
                    f'{user.name} claimed reserved book "{book.title}" from hidden inventory',
                    'info',
                    user_id
                )
            else:
                book.update_available_copies(-1)
                
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
            
            return Borrow.get_by_id(borrow_id), f"Book reserved! Please pick it up within {hold_days * 24} hours (by {pending_until})"
            
        except Exception as e:
            db.rollback()
            print(f"Error creating borrow: {e}")
            return None, f"Failed to create borrow request: {str(e)}"

    def return_book(self, condition='good', book_value=0.0) -> Tuple[bool, str]:
        """Return borrowed book with HIDDEN INVENTORY support."""
        if self.status != 'borrowed':
            return False, "Only borrowed books can be returned"

        from models.user import User
        from models.reservation import Reservation
        from models.system_log import SystemLog
        from models.fine import Fine

        db = get_db()
        return_timestamp = datetime.now()
        self.return_date = return_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        self.status = 'returned'
        self.condition = condition

        # Calculate fees
        due_timestamp = datetime.strptime(self.due_date, '%Y-%m-%d %H:%M:%S')
        self.late_fee = self.calculate_late_fee(due_timestamp, return_timestamp)
        self.damage_fee = self.calculate_damage_fee(condition, book_value)

        # Update borrow record
        db.execute('''
            UPDATE borrows
            SET status = ?, return_date = ?, condition = ?,
                late_fee = ?, damage_fee = ?
            WHERE id = ?
        ''', (self.status, self.return_date, self.condition,
              self.late_fee, self.damage_fee, self.id))

        # ========== CRITICAL: HIDDEN INVENTORY LOGIC ==========
        book = Book.get_by_id(self.book_id)
        if not book:
            db.rollback()
            return False, "Book not found"

        # Check for active reservations
        if Reservation.has_active_reservations(self.book_id):
            # Book goes to HIDDEN POOL
            next_reservation = Reservation.get_next_in_queue(self.book_id)
            
            # [DYNAMIC] Get Hold Time
            hold_days = SystemConfig.get_int('reservation_hold_time', 2)
            
            if next_reservation:
                success, msg = next_reservation.mark_ready(hold_hours=hold_days * 24)
                
                if success:
                    SystemLog.add(
                        'Book to Hidden Pool',
                        f'"{book.title}" returned to hidden pool. Next in queue notified.',
                        'info',
                        self.user_id
                    )
                else:
                    book.update_available_copies(1)
                    SystemLog.add(
                        'Reservation Notification Failed',
                        f'Failed to notify. Book returned to public pool. Error: {msg}',
                        'warning',
                        self.user_id
                    )
        else:
            book.update_available_copies(1)
            SystemLog.add(
                'Book to Public Pool',
                f'"{book.title}" returned to public inventory.',
                'info',
                self.user_id
            )

        # Apply fines
        total_fine = self.late_fee + self.damage_fee
        if total_fine > 0:
            user = User.get_by_id(self.user_id)
            if user:
                user.add_fine(total_fine)
                user.add_violation()
                fine_reason = f"Return fees (Late: {self.late_fee:,.0f}, Damage: {self.damage_fee:,.0f})"
                Fine.create(self.user_id, total_fine, fine_reason, self.id)

        db.commit()

        # Log return
        user = User.get_by_id(self.user_id)
        if user and book:
            SystemLog.add('Book Returned', f'{user.name} returned "{book.title}"', 'info', self.user_id)

        message = f"Book returned successfully"
        if total_fine > 0:
            message += f". Total fees: {total_fine:,.0f} VND"
        return True, message

    def renew(self, extension_days=None) -> Tuple[bool, str]:
        """Renew borrowed book with proper business rules."""
        if self.status != 'borrowed':
            return False, "Only borrowed books can be renewed"

        # [DYNAMIC] Get renewal limit
        limit = SystemConfig.get_int('renewal_limit', Config.MAX_RENEWAL_COUNT)
        if self.renewed_count >= limit:
            return False, f"Maximum renewal limit ({limit} times) reached"

        due_timestamp = datetime.strptime(self.due_date, '%Y-%m-%d %H:%M:%S')
        if datetime.now() > due_timestamp:
            return False, "Overdue books cannot be renewed"

        from models.reservation import Reservation
        if Reservation.has_active_reservations(self.book_id):
            return False, "Cannot renew: Someone has reserved this book"

        if extension_days is None:
            extension_days = Config.RENEWAL_EXTENSION_DAYS

        new_due_timestamp = due_timestamp + timedelta(days=extension_days)
        self.due_date = new_due_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        self.renewed_count += 1

        db = get_db()
        db.execute('''
            UPDATE borrows SET due_date = ?, renewed_count = ? WHERE id = ?
        ''', (self.due_date, self.renewed_count, self.id))
        db.commit()

        from models.system_log import SystemLog
        from models.user import User
        user = User.get_by_id(self.user_id)
        book = Book.get_by_id(self.book_id)
        if user and book:
            SystemLog.add(
                'Book Renewal',
                f'{user.name} renewed "{book.title}"',
                'info',
                self.user_id
            )

        return True, f"Book renewed successfully. New due date: {self.due_date}"
    
    def cancel(self) -> Tuple[bool, str]:
        """Cancel borrow request and handle inventory safely."""
        if self.status not in ['pending_pickup']:
            return False, "Only pending pickup requests can be cancelled"

        from models.reservation import Reservation
        from models.system_log import SystemLog
        
        db = get_db()
        
        self.status = 'cancelled'
        db.execute('UPDATE borrows SET status = ? WHERE id = ?', ('cancelled', self.id))

        book = Book.get_by_id(self.book_id)
        if not book:
            db.rollback()
            return False, "Book not found"

        next_reservation = Reservation.get_next_in_queue(self.book_id)
        
        if next_reservation:

            hold_days = SystemConfig.get_int('reservation_hold_time', 2)
            success, msg = next_reservation.mark_ready(hold_hours=hold_days * 24)
            
            if success:
                SystemLog.add('Borrow Cancelled - Cascaded', f'Book passed to next reserver.', 'info', self.user_id)
            else:
                book.update_available_copies(1)
        else:
            book.update_available_copies(1)
            SystemLog.add('Borrow Cancelled', f'Book returned to public.', 'info', self.user_id)

        db.commit()
        return True, "Borrow request cancelled successfully"

    @staticmethod
    def auto_cancel_expired_pickups():
        db = get_db()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
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

    @staticmethod
    def get_user_reserved_books(user_id: str) -> list:
        from models.reservation import Reservation
        return Reservation.get_user_reservations(user_id, status='waiting')

    @staticmethod
    def get_user_overdue_books(user_id: str) -> list:
        return Borrow.get_overdue_borrows(user_id)

    @staticmethod
    def get_upcoming_due_books(user_id: str, days: int = 3) -> list:
        return Borrow.get_upcoming_due(user_id, days)

    @staticmethod
    def get_user_borrowed_books(user_id: str) -> list:
        borrowed = Borrow.get_user_borrows(user_id, status='borrowed')
        pending = Borrow.get_user_borrows(user_id, status='pending_pickup')
        return borrowed + pending

    def get_book(self):
        return Book.get_by_id(self.book_id)
    
    def is_overdue(self):
        if self.status != 'borrowed':
            return False
        try:
            due_date = datetime.strptime(self.due_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            due_date = datetime.strptime(self.due_date, '%Y-%m-%d')
        return datetime.now() > due_date
    
    def get_overdue_days(self):
        if not self.is_overdue():
            return 0
        try:
            due_date = datetime.strptime(self.due_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            due_date = datetime.strptime(self.due_date, '%Y-%m-%d')
        return (datetime.now() - due_date).days
    
    def get_fine_amount(self):
        overdue_days = self.get_overdue_days()
        daily_rate = SystemConfig.get_float('late_fee_per_day', Config.LATE_FEE_DAILY)
        return overdue_days * daily_rate
    
    def get_user(self):
        from models.user import User
        return User.get_by_id(self.user_id)
    
    def to_dict(self):
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

    @staticmethod
    def get_by_id(borrow_id):
        db = get_db()
        row = db.execute('SELECT * FROM borrows WHERE id = ?', (borrow_id,)).fetchone()
        if row:
            return Borrow(**dict(row))
        return None
    
    @staticmethod
    def get_user_borrows(user_id, status=None):
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
        db = get_db()
        rows = db.execute(
            "SELECT * FROM borrows WHERE user_id = ? AND status IN ('borrowed', 'pending_pickup') ORDER BY borrow_date DESC",
            (user_id,)
        ).fetchall()
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def get_overdue_borrows(user_id=None):
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
        db = get_db()
        rows = db.execute(
            "SELECT * FROM borrows WHERE status = 'pending_pickup' ORDER BY borrow_date ASC"
        ).fetchall()
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def get_user_borrows_by_status(status):
        db = get_db()
        rows = db.execute(
            "SELECT * FROM borrows WHERE status = ? ORDER BY borrow_date DESC",
            (status,)
        ).fetchall()
        return [Borrow(**dict(row)) for row in rows]
    
    @staticmethod
    def get_all():
        db = get_db()
        rows = db.execute(
            "SELECT * FROM borrows ORDER BY borrow_date DESC"
        ).fetchall()
        return [Borrow(**dict(row)) for row in rows]

    @staticmethod
    def get_active_borrows_count() -> int:
        db = get_db()
        row = db.execute(
            "SELECT COUNT(*) as count FROM borrows WHERE status IN ('borrowed', 'pending_pickup', 'waiting')"
        ).fetchone()
        return row['count']

    @staticmethod
    def get_overdue_count() -> int:
        db = get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        row = db.execute(
            "SELECT COUNT(*) as count FROM borrows WHERE status = 'borrowed' AND due_date < ?",
            (today,)
        ).fetchone()
        return row['count']

    def approve_pickup(self) -> Tuple[bool, str]:
        """Approve and complete book pickup by user."""
        if self.status != 'pending_pickup':
            return False, "Only pending pickup requests can be approved"

        if self.pending_until:
            deadline = datetime.strptime(
                self.pending_until, '%Y-%m-%d %H:%M:%S'
            )
            if datetime.now() > deadline:
                self.cancel()
                return False, ("Pickup deadline has passed. Request has been cancelled.")

        db = get_db()
        now = datetime.now()
        self.status = 'borrowed'
        
        borrow_days = SystemConfig.get_int('borrow_duration', Config.BORROW_DURATION_DAYS)
        self.due_date = (now + timedelta(days=borrow_days)).strftime('%Y-%m-%d %H:%M:%S')

        db.execute('''
            UPDATE borrows
            SET status = ?, due_date = ?
            WHERE id = ?
        ''', ('borrowed', self.due_date, self.id))
        db.commit()

        from models.system_log import SystemLog
        from models.user import User
        user = User.get_by_id(self.user_id)
        book = Book.get_by_id(self.book_id)
        if user and book:
            SystemLog.add('Book Pickup Confirmed', f'{user.name} picked up "{book.title}"', 'info', self.user_id)

        return True, f"Book pickup confirmed! Due date: {self.due_date}"