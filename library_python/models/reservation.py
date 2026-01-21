from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import uuid
from models.database import get_db
from models.book import Book


class Reservation:
    """Represents a book reservation in the queue.
    
    Attributes:
        id (str): Unique reservation identifier.
        user_id (str): ID of user who made the reservation.
        book_id (str): ID of reserved book.
        reservation_date (str): When the reservation was made.
        status (str): Reservation status ('waiting', 'ready', 'expired', 'cancelled', 'completed').
        notified_date (str): When user was notified (for ready status).
        hold_until (str): Deadline for picking up (ready status).
        queue_position (int): Position in the reservation queue.
    """
    
    def __init__(self, id: str, user_id: str, book_id: str, 
                 reservation_date: str, status: str, 
                 notified_date: Optional[str], hold_until: Optional[str],
                 queue_position: int) -> None:
        """Initialize a Reservation instance."""
        self.id = id
        self.user_id = user_id
        self.book_id = book_id
        self.reservation_date = reservation_date
        self.status = status
        self.notified_date = notified_date
        self.hold_until = hold_until
        self.queue_position = queue_position
    
    @staticmethod
    def create(user_id: str, book_id: str) -> Tuple[Optional['Reservation'], str]:
        """Create a new reservation for a book."""
        db = get_db()
        
        book = Book.get_by_id(book_id)
        if not book:
            return None, "Book not found"
        
        if book.available_copies > 0:
            return None, "Book is available for immediate borrowing"
        
        existing = db.execute('''
            SELECT id FROM reservations 
            WHERE user_id = ? AND book_id = ? AND status = 'waiting'
        ''', (user_id, book_id)).fetchone()
        
        if existing:
            return None, "You already have a reservation for this book"
        
        max_position = db.execute('''
            SELECT MAX(queue_position) as max_pos FROM reservations
            WHERE book_id = ? AND status = 'waiting'
        ''', (book_id,)).fetchone()
        
        next_position = (max_position['max_pos'] or 0) + 1
        
        reservation_id = str(uuid.uuid4())
        reservation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            db.execute('''
                INSERT INTO reservations 
                (id, user_id, book_id, reservation_date, status, 
                 notified_date, hold_until, queue_position)
                VALUES (?, ?, ?, ?, 'waiting', NULL, NULL, ?)
            ''', (reservation_id, user_id, book_id, reservation_date, next_position))
            db.commit()
            
            from models.system_log import SystemLog
            from models.user import User
            user = User.get_by_id(user_id)
            if user:
                SystemLog.add(
                    'Book Reservation',
                    f'{user.name} reserved "{book.title}" (Position: {next_position})',
                    'info',
                    user_id
                )
            
            return Reservation.get_by_id(reservation_id), f"Book reserved successfully (Queue position: {next_position})"
        except Exception as e:
            print(f"Error creating reservation: {e}")
            return None, "Failed to create reservation"
    
    
    @staticmethod
    def get_by_id(reservation_id: str) -> Optional['Reservation']:
        """Get reservation by ID."""
        db = get_db()
        row = db.execute(
            'SELECT * FROM reservations WHERE id = ?', 
            (reservation_id,)
        ).fetchone()
        
        if row:
            return Reservation(**dict(row))
        return None
    
    @staticmethod
    def get_user_reservations(user_id: str, status: Optional[str] = None) -> List['Reservation']:
        """Get all reservations for a user."""
        db = get_db()
        
        if status:
            rows = db.execute('''
                SELECT * FROM reservations 
                WHERE user_id = ? AND status = ?
                ORDER BY reservation_date DESC
            ''', (user_id, status)).fetchall()
        else:
            rows = db.execute('''
                SELECT * FROM reservations 
                WHERE user_id = ?
                ORDER BY reservation_date DESC
            ''', (user_id,)).fetchall()
        
        return [Reservation(**dict(row)) for row in rows]
    
    @staticmethod
    def get_user_book_reservation(user_id: str, book_id: str) -> Optional['Reservation']:
        """Get user's reservation for a specific book."""
        db = get_db()
        row = db.execute('''
            SELECT * FROM reservations
            WHERE user_id = ? AND book_id = ? 
            ORDER BY reservation_date DESC
            LIMIT 1
        ''', (user_id, book_id)).fetchone()
        
        if row:
            return Reservation(**dict(row))
        return None
    
    @staticmethod
    def get_next_in_queue(book_id: str) -> Optional['Reservation']:
        """Get the next person in queue for a book."""
        db = get_db()
        row = db.execute('''
            SELECT * FROM reservations
            WHERE book_id = ? AND status = 'waiting'
            ORDER BY queue_position ASC
            LIMIT 1
        ''', (book_id,)).fetchone()
        
        if row:
            return Reservation(**dict(row))
        return None
    
    @staticmethod
    def has_active_reservations(book_id: str) -> bool:
        """Check if a book has any active reservations."""
        db = get_db()
        count = db.execute('''
            SELECT COUNT(*) as count FROM reservations
            WHERE book_id = ? AND status = 'waiting'
        ''', (book_id,)).fetchone()['count']
        
        return count > 0
    
    @staticmethod
    def get_all() -> List['Reservation']:
        """Get all reservations."""
        db = get_db()
        rows = db.execute('''
            SELECT * FROM reservations
            ORDER BY reservation_date DESC
        ''').fetchall()
        
        return [Reservation(**dict(row)) for row in rows]
    
    @staticmethod
    def get_ready_reservations_for_book(book_id: str) -> List['Reservation']:
        """Get all reservations marked as 'ready' for a specific book."""
        db = get_db()
        rows = db.execute('''
            SELECT * FROM reservations
            WHERE book_id = ? AND status = 'ready'
            ORDER BY notified_date ASC
        ''', (book_id,)).fetchall()

        return [Reservation(**dict(row)) for row in rows]
    
    def mark_ready(self, hold_hours: int = 48) -> Tuple[bool, str]:
        """Mark reservation as ready for pickup."""
        if self.status != 'waiting':
            return False, "Only waiting reservations can be marked ready"
        
        from models.notification import Notification
        from models.system_log import SystemLog
        
        db = get_db()
        now = datetime.now()
        hold_until = (now + timedelta(hours=hold_hours)).strftime('%Y-%m-%d %H:%M:%S')
        notified_date = now.strftime('%Y-%m-%d %H:%M:%S')
        
        self.status = 'ready'
        self.notified_date = notified_date
        self.hold_until = hold_until
        
        try:
            db.execute('''
                UPDATE reservations 
                SET status = ?, notified_date = ?, hold_until = ?
                WHERE id = ?
            ''', ('ready', notified_date, hold_until, self.id))

            book = Book.get_by_id(self.book_id)
            if book:
                notif = Notification.create(
                    user_id=self.user_id,
                    notification_type='success',
                    title='Reserved Book Available',
                    message=f'Your reserved book "{book.title}" is now available! '
                            f'Please pick it up before {hold_until}. '
                            f'If not picked up within {hold_hours} hours, the reservation will expire.'
                )
                
                if notif:
                    SystemLog.add(
                        'Reservation Ready',
                        f'User notified that "{book.title}" is ready for pickup. '
                        f'Hold until: {hold_until}',
                        'info',
                        self.user_id
                    )
            
            db.commit()
            return True, "Reservation marked as ready and notification sent"
        except Exception as e:
            db.rollback()
            return False, f"Failed to mark reservation as ready: {str(e)}"
    
    def cancel(self) -> Tuple[bool, str]:
        """Cancel the reservation with CASCADE to next in queue.
        
        REFACTORED: Implements "Hidden Inventory Cascade"
        - If cancelling a 'ready' reservation: Pass book to next in queue
        - If no one waiting: Return book to public inventory
        - If cancelling a 'waiting' reservation: Just remove from queue
        """
        if self.status not in ['waiting', 'ready']:
            return False, "Only waiting or ready reservations can be cancelled"
        
        from models.system_log import SystemLog
        
        db = get_db()
        book = Book.get_by_id(self.book_id)
        if not book:
            return False, "Book not found"
        
        was_ready = (self.status == 'ready')
        
        # Mark this reservation as cancelled
        self.status = 'cancelled'
        db.execute(
            'UPDATE reservations SET status = ? WHERE id = ?',
            ('cancelled', self.id)
        )
        
        # ========== CRITICAL: CASCADE LOGIC ==========
        if was_ready:
            # This person was holding a spot in hidden inventory
            # Check if there's someone else waiting
            next_reservation = Reservation.get_next_in_queue(self.book_id)
            
            if next_reservation:
                # CASCADE: Pass the book to next person in queue
                # Book stays in HIDDEN POOL - do NOT increase available_copies
                success, msg = next_reservation.mark_ready(hold_hours=48)
                
                if success:
                    SystemLog.add(
                        'Hidden Inventory Cascade',
                        f'Book "{book.title}" cascaded to next reserver after cancellation. '
                        f'Available copies NOT increased (still in hidden pool).',
                        'info',
                        None
                    )
                else:
                    # Cascade failed - return to public as fallback
                    book.update_available_copies(1)
                    SystemLog.add(
                        'Cascade Failed - Public Return',
                        f'Failed to cascade "{book.title}" to next reserver: {msg}. '
                        f'Book returned to public inventory.',
                        'warning',
                        None
                    )
            else:
                # NO ONE WAITING: Return book to PUBLIC INVENTORY
                book.update_available_copies(1)
                SystemLog.add(
                    'Hidden to Public Pool',
                    f'Book "{book.title}" returned from hidden pool to public inventory '
                    f'(last reservation cancelled, queue empty).',
                    'info',
                    None
                )
        else:
            # Cancelling a 'waiting' reservation
            # Reorder queue positions for remaining waiters
            db.execute('''
                UPDATE reservations
                SET queue_position = queue_position - 1
                WHERE book_id = ? AND status = 'waiting' AND queue_position > ?
            ''', (self.book_id, self.queue_position))
            
            SystemLog.add(
                'Waiting Reservation Cancelled',
                f'User cancelled waiting reservation for "{book.title}". '
                f'Queue reordered.',
                'info',
                self.user_id
            )
        
        db.commit()
        return True, "Reservation cancelled successfully"
    
    def mark_expired(self) -> Tuple[bool, str]:
        """Mark reservation as expired with CASCADE.
        
        REFACTORED: Uses same cascade logic as cancel()
        """
        if self.status != 'ready':
            return False, "Only ready reservations can expire"
        
        from models.system_log import SystemLog
        
        db = get_db()
        book = Book.get_by_id(self.book_id)
        if not book:
            return False, "Book not found"
        
        # Mark as expired
        self.status = 'expired'
        db.execute(
            'UPDATE reservations SET status = ? WHERE id = ?',
            ('expired', self.id)
        )
        
        # ========== CRITICAL: CASCADE LOGIC (same as cancel) ==========
        next_reservation = Reservation.get_next_in_queue(self.book_id)
        
        if next_reservation:
            # CASCADE to next person
            success, msg = next_reservation.mark_ready(hold_hours=48)
            
            if success:
                SystemLog.add(
                    'Expired Reservation Cascade',
                    f'Book "{book.title}" cascaded to next reserver after expiration. '
                    f'Available copies NOT increased.',
                    'info',
                    None
                )
            else:
                # Cascade failed - return to public
                book.update_available_copies(1)
                SystemLog.add(
                    'Cascade Failed - Public Return',
                    f'Failed to cascade "{book.title}" after expiration: {msg}. '
                    f'Book returned to public inventory.',
                    'warning',
                    None
                )
        else:
            # No one waiting - return to public
            book.update_available_copies(1)
            SystemLog.add(
                'Expired Reservation - Public Return',
                f'Book "{book.title}" returned to public inventory after expiration '
                f'(queue empty).',
                'info',
                None
            )
        
        db.commit()
        return True, "Reservation marked as expired"
    
    def complete(self) -> Tuple[bool, str]:
        """Mark reservation as completed (book borrowed).
        
        NOTE: This does NOT affect inventory because:
        - Book was already in hidden pool (available_copies already = 0)
        - When user creates borrow from this reservation, inventory stays the same
        """
        if self.status != 'ready':
            return False, "Only ready reservations can be completed"

        db = get_db()
        self.status = 'completed'

        db.execute(
            'UPDATE reservations SET status = ? WHERE id = ?',
            ('completed', self.id)
        )
        db.commit()

        from models.system_log import SystemLog
        book = Book.get_by_id(self.book_id)
        if book:
            SystemLog.add(
                'Reservation Completed',
                f'User claimed reserved book "{book.title}". '
                f'Book moved from hidden pool to borrowed status.',
                'info',
                self.user_id
            )

        return True, "Reservation completed"
    
    def get_book(self) -> Optional[Book]:
        """Get the book associated with this reservation."""
        return Book.get_by_id(self.book_id)
    
    def get_user(self):
        """Get the user associated with this reservation."""
        from models.user import User
        return User.get_by_id(self.user_id)
    
    def get_queue_position(self) -> int:
        """Get current position in the queue."""
        return self.queue_position
    
    def to_dict(self) -> dict:
        """Convert reservation to dictionary."""
        book = Book.get_by_id(self.book_id)
        
        return {
            'id': self.id,
            'user_id': self.user_id,
            'book_id': self.book_id,
            'book': book.to_dict() if book else None,
            'reservation_date': self.reservation_date,
            'status': self.status,
            'notified_date': self.notified_date,
            'hold_until': self.hold_until,
            'queue_position': self.queue_position
        }