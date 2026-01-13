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
    def create(user_id, book_id, rating, comment):
        """Create a new review"""
        db = get_db()
        
        # Check if user already reviewed this book
        existing = db.execute('''
            SELECT id FROM reviews 
            WHERE user_id = ? AND book_id = ?
        ''', (user_id, book_id)).fetchone()
        
        if existing:
            return None, "You have already reviewed this book"
        
        # Validate rating
        if rating < 1 or rating > 5:
            return None, "Rating must be between 1 and 5"
        
        review_id = str(uuid.uuid4())
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            db.execute('''
                INSERT INTO reviews (id, user_id, book_id, rating, comment, date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (review_id, user_id, book_id, rating, comment, date))
            db.commit()
            
            # Update book rating
            Review.update_book_rating(book_id)
            
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
    
    def update(self, rating, comment):
        """Update a review"""
        if rating < 1 or rating > 5:
            return False, "Rating must be between 1 and 5"
        
        db = get_db()
        self.rating = rating
        self.comment = comment
        
        db.execute('''
            UPDATE reviews 
            SET rating = ?, comment = ? 
            WHERE id = ?
        ''', (rating, comment, self.id))
        db.commit()
        
        # Update book rating
        Review.update_book_rating(self.book_id)
        
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
    
    # ==================== SERVICE METHODS (Merged from ReviewService) ====================
    
    @staticmethod
    def submit_review(user_id: str, book_id: str, rating, comment: str) -> tuple:
        """Submit a new review with validation and logging.
        
        Args:
            user_id: ID of user submitting the review.
            book_id: ID of book being reviewed.
            rating: Star rating (1-5).
            comment: Review comment.
            
        Returns:
            Tuple of (Review or None, message).
        """
        from models.book import Book
        from models.system_log import SystemLog
        
        # Verify user exists
        user = User.get_by_id(user_id)
        if not user:
            return None, "Invalid user"
        
        # Verify book exists
        book = Book.get_by_id(book_id)
        if not book:
            return None, "Book not found"
        
        # Validate rating
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return None, "Rating must be between 1 and 5 stars"
        except (ValueError, TypeError):
            return None, "Invalid rating"
        
        # Create review
        review, message = Review.create(user_id, book_id, rating, comment)
        if review:
            SystemLog.add(
                'Book Review',
                f'{user.name} reviewed "{book.title}" with {rating} stars',
                'info',
                user_id
            )
        return review, message
    
    @staticmethod
    def get_book_reviews_with_details(book_id: str, limit=None) -> list:
        """Get all reviews for a book with user details.
        
        Args:
            book_id: ID of the book.
            limit: Maximum number of reviews.
            
        Returns:
            List of review dictionaries.
        """
        reviews = Review.get_by_book(book_id, limit)
        return [review.to_dict() for review in reviews]
    
    @staticmethod
    def get_user_reviews_with_details(user_id: str) -> list:
        """Get all reviews by a user with book details.
        
        Args:
            user_id: ID of the user.
            
        Returns:
            List of review dictionaries with book details.
        """
        from models.book import Book
        
        reviews = Review.get_by_user(user_id)
        result = []
        for review in reviews:
            review_dict = review.to_dict()
            book = Book.get_by_id(review.book_id)
            if book:
                review_dict['book_title'] = book.title
                review_dict['book_cover'] = book.cover_url
            result.append(review_dict)
        return result
    
    @staticmethod
    def user_can_review(user_id: str, book_id: str) -> bool:
        """Check if user can review a book.
        
        Args:
            user_id: ID of the user.
            book_id: ID of the book.
            
        Returns:
            True if user hasn't reviewed yet.
        """
        return not Review.user_has_reviewed(user_id, book_id)
    
    @staticmethod
    def update_review_by_user(review_id: str, user_id: str, rating, comment: str) -> tuple:
        """Update an existing review.
        
        Args:
            review_id: ID of review to update.
            user_id: ID of user (for ownership verification).
            rating: New rating.
            comment: New comment.
            
        Returns:
            Tuple of (success, message).
        """
        review = Review.get_by_id(review_id)
        
        if not review:
            return False, "Review not found"
        
        if review.user_id != user_id:
            return False, "You can only edit your own reviews"
        
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return False, "Rating must be between 1 and 5 stars"
        except (ValueError, TypeError):
            return False, "Invalid rating"
        
        return review.update(rating, comment)
    
    @staticmethod
    def delete_review_by_user(review_id: str, user_id: str, user_role: str) -> tuple:
        """Delete a review.
        
        Args:
            review_id: ID of review to delete.
            user_id: ID of user (for ownership verification).
            user_role: Role of user (admin can delete any).
            
        Returns:
            Tuple of (success, message).
        """
        review = Review.get_by_id(review_id)
        
        if not review:
            return False, "Review not found"
        
        if review.user_id != user_id and user_role != 'admin':
            return False, "You don't have permission to delete this review"
        
        return Review.delete(review_id)
    
    @staticmethod
    def get_book_rating_stats(book_id: str) -> dict:
        """Get rating statistics for a book.
        
        Args:
            book_id: ID of the book.
            
        Returns:
            Dictionary with average, count, and distribution.
        """
        reviews = Review.get_by_book(book_id)
        
        if not reviews:
            return {
                'average': 0,
                'count': 0,
                'distribution': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            }
        
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        total = 0
        
        for review in reviews:
            distribution[review.rating] += 1
            total += review.rating
        
        return {
            'average': round(total / len(reviews), 1),
            'count': len(reviews),
            'distribution': distribution
        }
