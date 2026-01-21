from typing import Optional, List, Dict, Any, Tuple
from models.database import get_db


class Book:
    """Represents a book in the library system.
    
    This class handles all book-related operations including searching,
    borrowing management, and inventory tracking.
    
    Attributes:
        id (str): Unique identifier for the book.
        title (str): Book title.
        author (str): Book author name.
        category (str): Book category/genre.
        publisher (str): Publisher name.
        year (int): Publication year.
        language (str): Book language.
        isbn (str): ISBN number.
        description (str): Book description/summary.
        cover_url (str): URL or path to cover image.
        total_copies (int): Total number of copies owned.
        available_copies (int): Number of copies currently available.
        shelf_location (str): Physical shelf location.
        rating (float): Average rating from reviews (0.0-5.0).
        borrow_count (int): Total times this book has been borrowed.
    """
    
    def __init__(self, id: str, title: str, author: str, category: str,
                 publisher: str, year: int, language: str, isbn: str,
                 description: str, cover_url: str, total_copies: int,
                 available_copies: int, shelf_location: str,
                 rating: float, borrow_count: int) -> None:
        """Initialize a Book instance."""
        self.id = id
        self.title = title
        self.author = author
        self.category = category
        self.publisher = publisher
        self.year = int(year)
        self.language = language
        self.isbn = isbn
        self.description = description
        self.cover_url = cover_url
        self.total_copies = int(total_copies)
        self.available_copies = int(available_copies)
        self.shelf_location = shelf_location
        self.rating = float(rating)
        self.borrow_count = int(borrow_count)
    
    @staticmethod
    def get_by_id(book_id: str) -> Optional['Book']:
        """Retrieve a book by its ID."""
        db = get_db()
        row = db.execute('''
            SELECT id, title, author, category, publisher, year, language, isbn,
                   description, cover_url, total_copies, available_copies, 
                   shelf_location, rating, borrow_count
            FROM books WHERE id = ?
        ''', (book_id,)).fetchone()
        if row:
            return Book(**dict(row))
        return None
    
    @staticmethod
    def get_by_isbn(isbn: str) -> Optional['Book']:
        """Retrieve a book by its ISBN number."""
        db = get_db()
        row = db.execute('''
            SELECT id, title, author, category, publisher, year, language, isbn,
                   description, cover_url, total_copies, available_copies, 
                   shelf_location, rating, borrow_count
            FROM books WHERE isbn = ?
        ''', (isbn,)).fetchone()
        if row:
            return Book(**dict(row))
        return None
    
    @staticmethod
    def get_all(limit: Optional[int] = None) -> List['Book']:
        """Retrieve all books from the database."""
        db = get_db()
        query = '''SELECT id, title, author, category, publisher, year, language, isbn,
                          description, cover_url, total_copies, available_copies, 
                          shelf_location, rating, borrow_count
                   FROM books'''
        if limit:
            query += f' LIMIT {limit}'
        
        rows = db.execute(query).fetchall()
        return [Book(**dict(row)) for row in rows]
    
    @staticmethod
    def search(query: str = '', search_by: str = 'title',
               sort_by: str = 'title', category: str = '') -> List['Book']:
        """Search for books with various filters and sorting options."""
        db = get_db()
        
        sql = '''SELECT id, title, author, category, publisher, year, language, isbn,
                        description, cover_url, total_copies, available_copies, 
                        shelf_location, rating, borrow_count
                 FROM books WHERE 1=1'''
        params = []
        
        # Apply search filters
        if query:
            if search_by == 'title':
                sql += ' AND LOWER(title) LIKE ?'
                params.append(f'%{query.lower()}%')
            elif search_by == 'author':
                sql += ' AND LOWER(author) LIKE ?'
                params.append(f'%{query.lower()}%')
            elif search_by == 'category':
                sql += ' AND LOWER(category) LIKE ?'
                params.append(f'%{query.lower()}%')
        
        # Apply category filter
        if category:
            sql += ' AND category = ?'
            params.append(category)
        
        # Apply sorting
        if sort_by == 'title':
            sql += ' ORDER BY title ASC'
        elif sort_by == 'author':
            sql += ' ORDER BY author ASC'
        elif sort_by == 'year':
            sql += ' ORDER BY year DESC'
        elif sort_by == 'rating':
            sql += ' ORDER BY rating DESC'
        elif sort_by == 'popular':
            sql += ' ORDER BY borrow_count DESC'
        elif sort_by == 'new':
            sql += ' ORDER BY year DESC'
        
        rows = db.execute(sql, params).fetchall()
        return [Book(**dict(row)) for row in rows]
    
    @staticmethod
    def get_by_category(category: str, limit: Optional[int] = None) -> List['Book']:
        """Retrieve books filtered by category."""
        db = get_db()
        query = '''SELECT id, title, author, category, publisher, year, language, isbn,
                          description, cover_url, total_copies, available_copies, 
                          shelf_location, rating, borrow_count
                   FROM books WHERE category = ?'''
        if limit:
            query += f' LIMIT {limit}'
        
        rows = db.execute(query, (category,)).fetchall()
        return [Book(**dict(row)) for row in rows]
    
    @staticmethod
    def get_new_arrivals(limit: int = 10) -> List['Book']:
        """Retrieve newest books sorted by publication year."""
        db = get_db()
        rows = db.execute('''
            SELECT id, title, author, category, publisher, year, language, isbn,
                   description, cover_url, total_copies, available_copies, 
                   shelf_location, rating, borrow_count
            FROM books ORDER BY year DESC LIMIT ?
        ''', (limit,)).fetchall()
        return [Book(**dict(row)) for row in rows]
    
    @staticmethod
    def get_most_borrowed(limit: int = 10) -> List['Book']:
        """Retrieve most popular books by borrow count."""
        db = get_db()
        rows = db.execute('''
            SELECT id, title, author, category, publisher, year, language, isbn,
                   description, cover_url, total_copies, available_copies, 
                   shelf_location, rating, borrow_count
            FROM books ORDER BY borrow_count DESC LIMIT ?
        ''', (limit,)).fetchall()
        return [Book(**dict(row)) for row in rows]
    
    @staticmethod
    def get_top_rated(limit: int = 10) -> List['Book']:
        """Retrieve highest rated books."""
        db = get_db()
        rows = db.execute('''
            SELECT id, title, author, category, publisher, year, language, isbn,
                   description, cover_url, total_copies, available_copies, 
                   shelf_location, rating, borrow_count
            FROM books ORDER BY rating DESC LIMIT ?
        ''', (limit,)).fetchall()
        return [Book(**dict(row)) for row in rows]
    
    @staticmethod
    def get_all_categories() -> List[str]:
        """Retrieve all unique book categories."""
        db = get_db()
        rows = db.execute(
            'SELECT DISTINCT category FROM books ORDER BY category'
        ).fetchall()
        return [row['category'] for row in rows]
    
    def update_available_copies(self, change: int) -> None:
        """Update the available copies count.
        
        Ensures the count stays within valid bounds (0 to total_copies).
        
        Args:
            change: Amount to change (positive or negative).
        """
        self.available_copies += change
        if self.available_copies < 0:
            self.available_copies = 0
        if self.available_copies > self.total_copies:
            self.available_copies = self.total_copies
        
        db = get_db()
        db.execute(
            'UPDATE books SET available_copies = ? WHERE id = ?',
            (self.available_copies, self.id)
        )
        db.commit()
    
    def increment_borrow_count(self) -> None:
        """Increment the borrow count by 1."""
        self.borrow_count += 1
        db = get_db()
        db.execute(
            'UPDATE books SET borrow_count = ? WHERE id = ?',
            (self.borrow_count, self.id)
        )
        db.commit()
    
    def update_rating(self) -> None:
        """Recalculate and update average rating from all reviews."""
        db = get_db()
        row = db.execute(
            'SELECT AVG(rating) as avg_rating FROM reviews WHERE book_id = ?',
            (self.id,)
        ).fetchone()
        
        if row and row['avg_rating']:
            self.rating = round(float(row['avg_rating']), 1)
            db.execute(
                'UPDATE books SET rating = ? WHERE id = ?',
                (self.rating, self.id)
            )
            db.commit()
    
    @staticmethod
    def create(title: str, author: str, category: str, publisher: str,
               year: int, language: str, isbn: str, description: str,
               cover_url: str, total_copies: int, shelf_location: str) -> Optional['Book']:
        """Create a new book in the database."""
        import uuid
        db = get_db()
        
        book_id = str(uuid.uuid4())
        
        try:
            db.execute('''
                INSERT INTO books (id, title, author, category, publisher, year, language,
                                 isbn, description, cover_url, total_copies, available_copies,
                                 shelf_location, rating, borrow_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0)
            ''', (book_id, title, author, category, publisher, year, language, isbn,
                  description, cover_url, total_copies, total_copies, shelf_location))
            db.commit()
            
            return Book.get_by_id(book_id)
        except Exception as e:
            print(f"Error creating book: {e}")
            return None
    
    def delete(self) -> None:
        """Delete this book from the database."""
        db = get_db()
        db.execute('DELETE FROM books WHERE id = ?', (self.id,))
        db.commit()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert book to dictionary representation."""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'category': self.category,
            'publisher': self.publisher,
            'year': self.year,
            'language': self.language,
            'isbn': self.isbn,
            'description': self.description,
            'cover_url': self.cover_url,
            'total_copies': self.total_copies,
            'available_copies': self.available_copies,
            'shelf_location': self.shelf_location,
            'rating': self.rating,
            'borrow_count': self.borrow_count
        }
    
    @staticmethod
    def get_total_count() -> int:
        """Get total number of books in catalog."""
        db = get_db()
        row = db.execute('SELECT COUNT(*) as count FROM books').fetchone()
        return row['count']
    
    def update_fields(self, **kwargs) -> Tuple[bool, str]:
        """Update book information.
        
        REFACTORED: Intercepts manual 'available_copies' updates to respect
        the 'Hidden Inventory' logic.
        
        If an Admin manually increases copies (e.g., from 0 to 5):
        1. Checks for waiting reservations.
        2. Automatically assigns new copies to reservations (Hidden Pool).
        3. Only the remaining copies become Public.
        
        Args:
            **kwargs: Fields to update (title, author, available_copies, etc.).
            
        Returns:
            Tuple of (success: bool, message: str).
        """
        db = get_db()
        
        # ========== CRITICAL: INTERCEPT MANUAL INVENTORY UPDATE ==========
        if 'available_copies' in kwargs:
            try:
                target_copies = int(kwargs['available_copies'])
                current_copies = self.available_copies
                added_copies = target_copies - current_copies
                
                # Only if we are ADDING copies, we check reservations
                if added_copies > 0:
                    from models.reservation import Reservation
                    from models.system_log import SystemLog
                    
                    # Try to absorb these new copies into reservations
                    copies_absorbed_by_reservations = 0
                    
                    for _ in range(added_copies):
                        # Get next waiting person
                        next_res = Reservation.get_next_in_queue(self.id)
                        
                        if next_res:
                            # Assign copy to this person (Hidden Inventory)
                            success, _ = next_res.mark_ready(hold_hours=48)
                            if success:
                                copies_absorbed_by_reservations += 1
                        else:
                            # No more reservations waiting
                            break
                    
                    if copies_absorbed_by_reservations > 0:
                        # Logic:
                        # Admin wanted to set Total = 5 (Target)
                        # Current was 0. Added = 5.
                        # Absorbed = 2 (assigned to reservers).
                        # New Public Count should be: Target - Absorbed = 3.
                        
                        kwargs['available_copies'] = target_copies - copies_absorbed_by_reservations
                        
                        # Log this automatic action
                        SystemLog.add(
                            'Inventory Update Intercepted',
                            f'Admin added {added_copies} copies. System automatically assigned '
                            f'{copies_absorbed_by_reservations} copies to waiting reservations. '
                            f'Public inventory set to {kwargs["available_copies"]}.',
                            'system',
                            None # Or current user ID if available in context
                        )
            except ValueError:
                return False, "Invalid number for available copies"

        # ========== STANDARD UPDATE LOGIC ==========
        fields = []
        values = []
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                fields.append(f"{key} = ?")
                values.append(value)
                setattr(self, key, value)
        
        if not fields:
            return False, "No fields to update"
        
        values.append(self.id)
        query = f"UPDATE books SET {', '.join(fields)} WHERE id = ?"
        
        try:
            db.execute(query, values)
            db.commit()
            return True, "Book updated successfully"
        except Exception as e:
            return False, f"Failed to update book: {e}"