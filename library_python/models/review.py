"""Review model for book reviews and ratings.

This module handles creating, retrieving, and managing
book reviews and ratings in the library system.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from models.database import get_db


class Review:
    """Represents a book review with rating and comment.

    Attributes:
        id: Unique review identifier.
        user_id: ID of the user who wrote the review.
        book_id: ID of the book being reviewed.
        rating: Rating value (1-5).
        comment: Review comment text.
        date: When the review was created.
    """

    def __init__(self, id: str, user_id: str, book_id: str,
                 rating: int, comment: str, date: str) -> None:
        """Initialize a Review instance."""
        self.id = id
        self.user_id = user_id
        self.book_id = book_id
        self.rating = int(rating)
        self.comment = comment
        self.date = date
    
    @staticmethod
    def create(user_id: str, book_id: str, rating: int,
              comment: str) -> Tuple[Optional['Review'], str]:
        """Create a new review and automatically update book rating."""
        db = get_db()
        
        # Verify user and book existence before creation
        from models.user import User
        from models.book import Book
        
        if not User.get_by_id(user_id):
            return None, "Invalid user"
        if not Book.get_by_id(book_id):
            return None, "Book not found"
            
        # Check if user already reviewed this book
        existing = db.execute('''
            SELECT id FROM reviews
            WHERE user_id = ? AND book_id = ?
        ''', (user_id, book_id)).fetchone()

        if existing:
            return None, "You have already reviewed this book"

        # Validate rating
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return None, "Rating must be between 1 and 5"
        except (ValueError, TypeError):
             return None, "Invalid rating format"

        review_id = str(uuid.uuid4())
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            db.execute('''
                INSERT INTO reviews (id, user_id, book_id, rating, comment, date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (review_id, user_id, book_id, rating, comment, date))
            db.commit()

            # Automatically update book rating
            book = Book.get_by_id(book_id)
            if book:
                book.update_rating()
                
            # Log action
            from models.system_log import SystemLog
            user = User.get_by_id(user_id)
            if user and book:
                SystemLog.add(
                    'Book Review',
                    f'{user.name} reviewed "{book.title}" with {rating} stars',
                    'info',
                    user_id
                )

            return Review.get_by_id(review_id), "Review submitted successfully"
        except Exception as e:
            print(f"Error creating review: {e}")
            return None, "Failed to submit review"
    
    @staticmethod
    def get_by_id(review_id):
        """Get review by ID"""
        db = get_db()
        row = db.execute('SELECT * FROM reviews WHERE id = ?', (review_id,)).fetchone()
        if row:
            return Review(**dict(row))
        return None
    
    @staticmethod
    def get_by_book(book_id, limit=None):
        """Get all reviews for a book"""
        db = get_db()
        
        if limit:
            rows = db.execute('''
                SELECT * FROM reviews 
                WHERE book_id = ? 
                ORDER BY date DESC 
                LIMIT ?
            ''', (book_id, limit)).fetchall()
        else:
            rows = db.execute('''
                SELECT * FROM reviews 
                WHERE book_id = ? 
                ORDER BY date DESC
            ''', (book_id,)).fetchall()
        
        return [Review(**dict(row)) for row in rows]
    
    @staticmethod
    def get_by_user(user_id):
        """Get all reviews by a user"""
        db = get_db()
        rows = db.execute('''
            SELECT * FROM reviews 
            WHERE user_id = ? 
            ORDER BY date DESC
        ''', (user_id,)).fetchall()
        
        return [Review(**dict(row)) for row in rows]
    
    @staticmethod
    def user_has_reviewed(user_id, book_id):
        """Check if user has already reviewed a book"""
        db = get_db()
        row = db.execute('''
            SELECT id FROM reviews 
            WHERE user_id = ? AND book_id = ?
        ''', (user_id, book_id)).fetchone()
        
        return row is not None
    
    @staticmethod
    def update_book_rating(book_id):
        """Recalculate and update book's average rating"""
        db = get_db()
        
        # Calculate average rating
        row = db.execute('''
            SELECT AVG(rating) as avg_rating, COUNT(*) as count
            FROM reviews 
            WHERE book_id = ?
        ''', (book_id,)).fetchone()
        
        if row and row['count'] > 0:
            avg_rating = round(row['avg_rating'], 1)
            db.execute('''
                UPDATE books 
                SET rating = ? 
                WHERE id = ?
            ''', (avg_rating, book_id))
            db.commit()
    
    @staticmethod
    def delete(review_id):
        """Delete a review"""
        db = get_db()
        
        # Get book_id before deleting
        review = Review.get_by_id(review_id)
        if not review:
            return False, "Review not found"
        
        book_id = review.book_id
        
        db.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        db.commit()
        
        # Update book rating
        Review.update_book_rating(book_id)
        
        return True, "Review deleted successfully"
    
    def update(self, rating: int, comment: str) -> Tuple[bool, str]:
        """Update a review and automatically update book rating."""
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return False, "Rating must be between 1 and 5 stars"
        except (ValueError, TypeError):
            return False, "Invalid rating"

        db = get_db()
        self.rating = rating
        self.comment = comment

        db.execute('''
            UPDATE reviews
            SET rating = ?, comment = ?
            WHERE id = ?
        ''', (rating, comment, self.id))
        db.commit()

        # Automatically update book rating
        from models.book import Book
        book = Book.get_by_id(self.book_id)
        if book:
            book.update_rating()

        return True, "Review updated successfully"

    def get_user(self):
        """Get user who wrote the review."""
        from models.user import User
        return User.get_by_id(self.user_id)

    def to_dict(self):
        """Convert review to dictionary"""
        user = self.get_user()
        
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': user.name if user else 'Unknown',
            'user_role': user.role if user else 'user',
            'book_id': self.book_id,
            'rating': self.rating,
            'comment': self.comment,
            'date': self.date
        }