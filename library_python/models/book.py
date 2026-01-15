"""Book model module.

This module defines the Book model for managing library books
in the system.
"""
from typing import Optional, List, Dict, Any
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
        """Initialize a Book instance.
        
        Args:
            id: Unique identifier for the book.
            title: Book title.
            author: Author name.
            category: Book category.
            publisher: Publisher name.
            year: Publication year.
            language: Book language.
            isbn: ISBN number.
            description: Book description.
            cover_url: Cover image URL/path.
            total_copies: Total copies owned.
            available_copies: Available copies count.
            shelf_location: Physical location.
            rating: Average rating.
            borrow_count: Times borrowed.
        """
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
        """Retrieve a book by its ID.
        
        Args:
            book_id: The unique identifier of the book.
            
        Returns:
            Book instance if found, None otherwise.
        """
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
        """Retrieve a book by its ISBN number.
        
        Args:
            isbn: The ISBN number to search for.
            
        Returns:
            Book instance if found, None otherwise.
        """
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
        """Retrieve all books from the database.
        
        Args:
            limit: Maximum number of books to return. None for all books.
            
        Returns:
            List of Book instances.
        """
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
        """Search for books with various filters and sorting options.
        
        Args:
            query: Search query string.
            search_by: Field to search in ('title', 'author', 'category').
            sort_by: Sorting criteria ('title', 'author', 'year', 'rating',
                    'popular', 'new').
            category: Filter by specific category.
            
        Returns:
            List of matching Book instances.
            
        Example:
            >>> books = Book.search(query='python', search_by='title', 
            ...                     sort_by='rating')
        """
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
        """Retrieve books filtered by category.
        
        Args:
            category: Category name to filter by.
            limit: Maximum number of results. None for all.
            
        Returns:
            List of Book instances in the specified category.
        """
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
        """Retrieve newest books sorted by publication year.
        
        Args:
            limit: Maximum number of books to return.
            
        Returns:
            List of newest Book instances.
        """
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
        """Retrieve most popular books by borrow count.
        
        Args:
            limit: Maximum number of books to return.
            
        Returns:
            List of most borrowed Book instances.
        """
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
        """Retrieve highest rated books.
        
        Args:
            limit: Maximum number of books to return.
            
        Returns:
            List of top-rated Book instances.
        """
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
        """Retrieve all unique book categories.
        
        Returns:
            Sorted list of category names.
        """
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
            
        Example:
            >>> book.update_available_copies(-1)  # Borrowed
            >>> book.update_available_copies(1)   # Returned
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
        """Increment the borrow count by 1.
        
        Called when a book is successfully borrowed.
        """
        self.borrow_count += 1
        db = get_db()
        db.execute(
            'UPDATE books SET borrow_count = ? WHERE id = ?',
            (self.borrow_count, self.id)
        )
        db.commit()
    
    def update_rating(self) -> None:
        """Recalculate and update average rating from all reviews.
        
        Fetches all reviews for this book and updates the rating field.
        """
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
        """Create a new book in the database.
        
        Args:
            title: Book title.
            author: Author name.
            category: Book category.
            publisher: Publisher name.
            year: Publication year.
            language: Book language.
            isbn: ISBN number.
            description: Book description.
            cover_url: Cover image URL/path.
            total_copies: Total number of copies.
            shelf_location: Physical shelf location.
            
        Returns:
            New Book instance if successful, None otherwise.
        """
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
        """Delete this book from the database.
        
        Warning: This will permanently remove the book record.
        """
        db = get_db()
        db.execute('DELETE FROM books WHERE id = ?', (self.id,))
        db.commit()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert book to dictionary representation.
        
        Returns:
            Dictionary containing all book attributes.
        """
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
    
    # ==================== SERVICE METHODS (Merged from BookService) ====================
    
    @staticmethod
    def get_total_count() -> int:
        """Get total number of books in catalog.
        
        Returns:
            Total book count.
        """
        db = get_db()
        row = db.execute('SELECT COUNT(*) as count FROM books').fetchone()
        return row['count']
    
    def update_fields(self, **kwargs) -> tuple:
        """Update book information.
        
        Args:
            **kwargs: Fields to update (title, author, etc.).
            
        Returns:
            Tuple of (success: bool, message: str).
        """
        db = get_db()
        
        # Build update query dynamically
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
