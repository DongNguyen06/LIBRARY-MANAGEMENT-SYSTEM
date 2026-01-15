"""
Reservation model for book reservation queue management.

This module handles the reservation queue system where users can reserve
books that are currently out of stock. When a book is returned, the system
automatically notifies users in the queue order (FIFO).
"""
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
        status (str): Reservation status ('waiting', 'ready', 'expired', 'cancelled').
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
        """Create a new reservation for a book.
        
        Args:
            user_id: ID of user making the reservation.
            book_id: ID of book to reserve.
            
        Returns:
            Tuple of (Reservation instance, message).
        """
        db = get_db()
        
        # Check if book exists
        book = Book.get_by_id(book_id)
        if not book:
            return None, "Book not found"
        
        # Check if book is available (shouldn't reserve if available)
        if book.available_copies > 0:
            return None, "Book is available for immediate borrowing"
        
        # Check if user already has a reservation for this book
        existing = db.execute('''
            SELECT id FROM reservations 
            WHERE user_id = ? AND book_id = ? AND status = 'waiting'
        ''', (user_id, book_id)).fetchone()
        
        if existing:
            return None, "You already have a reservation for this book"
        
        # Get next queue position
        max_position = db.execute('''
            SELECT MAX(queue_position) as max_pos FROM reservations
            WHERE book_id = ? AND status = 'waiting'
        ''', (book_id,)).fetchone()
        
        next_position = (max_position['max_pos'] or 0) + 1
        
        # Create reservation
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
            
            # Log reservation
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
        """Get all reservations for a user.
        
        Args:
            user_id: User ID.
            status: Filter by status (optional).
            
        Returns:
            List of Reservation objects.
        """
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
        """Get user's reservation for a specific book.
        
        Args:
            user_id: User ID.
            book_id: Book ID.
            
        Returns:
            Reservation instance or None.
        """
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
        """Get the next person in queue for a book.
        
        Args:
            book_id: Book ID.
            
        Returns:
            First waiting reservation or None.
        """
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
        """Check if a book has any active reservations.
        
        Args:
            book_id: Book ID to check.
            
        Returns:
            True if there are waiting reservations.
        """
        db = get_db()
        count = db.execute('''
            SELECT COUNT(*) as count FROM reservations
            WHERE book_id = ? AND status = 'waiting'
        ''', (book_id,)).fetchone()['count']
        
        return count > 0
    
    @staticmethod
    def get_all() -> List['Reservation']:
        """Get all reservations.
        
        Returns:
            List of all Reservation instances ordered by reservation date.
        """
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
        """Mark reservation as ready for pickup.
        
        Args:
            hold_hours: How many hours to hold the book (default 48).
            
        Returns:
            Tuple of (success, message).
        """
        if self.status != 'waiting':
            return False, "Only waiting reservations can be marked ready"
        
        db = get_db()
        now = datetime.now()
        hold_until = (now + timedelta(hours=hold_hours)).strftime('%Y-%m-%d %H:%M:%S')
        notified_date = now.strftime('%Y-%m-%d %H:%M:%S')
        
        self.status = 'ready'
        self.notified_date = notified_date
        self.hold_until = hold_until
        
        db.execute('''
            UPDATE reservations 
            SET status = ?, notified_date = ?, hold_until = ?
            WHERE id = ?
        ''', ('ready', notified_date, hold_until, self.id))
        db.commit()
        
        # Send notification to user
        from models.notification import Notification
        from models.book import Book
        book = Book.get_by_id(self.book_id)
        if book:
            Notification.create(
                self.user_id,
                'success',
                'Reserved Book Available',
                f'Your reserved book "{book.title}" is now available! '
                f'Please pick it up before {hold_until}.'
            )
        
        return True, "Reservation marked as ready"
    
    def cancel(self) -> Tuple[bool, str]:
        """Cancel the reservation.
        
        Returns:
            Tuple of (success, message).
        """
        if self.status not in ['waiting', 'ready']:
            return False, "Only waiting or ready reservations can be cancelled"
        
        db = get_db()
        
        # Update status
        self.status = 'cancelled'
        db.execute(
            'UPDATE reservations SET status = ? WHERE id = ?',
            ('cancelled', self.id)
        ).fetchone()
        
        # Reorder queue if this was waiting
        if self.status == 'waiting':
            db.execute('''
                UPDATE reservations
                SET queue_position = queue_position - 1
                WHERE book_id = ? AND status = 'waiting' AND queue_position > ?
            ''', (self.book_id, self.queue_position))
        
        db.commit()
        
        return True, "Reservation cancelled successfully"
    
    def mark_expired(self) -> Tuple[bool, str]:
        """Mark reservation as expired (didn't pick up in time).
        
        Returns:
            Tuple of (success, message).
        """
        if self.status != 'ready':
            return False, "Only ready reservations can expire"
        
        db = get_db()
        self.status = 'expired'
        
        db.execute(
            'UPDATE reservations SET status = ? WHERE id = ?',
            ('expired', self.id)
        )
        db.commit()
        
        return True, "Reservation marked as expired"
    
    def complete(self) -> Tuple[bool, str]:
        """Mark reservation as completed (book borrowed)."""
        if self.status != 'ready':
            return False, "Only ready reservations can be completed"

        db = get_db()
        self.status = 'completed'

        db.execute(
            'UPDATE reservations SET status = ? WHERE id = ?',
            ('completed', self.id)
        )
        db.commit()

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
