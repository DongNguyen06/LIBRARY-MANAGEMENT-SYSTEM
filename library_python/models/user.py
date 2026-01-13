"""User model module.

This module defines the User, Staff, and Admin models for managing library members,
including authentication, favorites, and account management.

Class Hierarchy:
    User (base class) - Regular library members
    ├── Staff - Library staff with additional permissions
    └── Admin - System administrators with full access
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from werkzeug.security import generate_password_hash, check_password_hash
from models.database import get_db


class User:
    """Represents a library user (member, staff, or admin).
    
    This class handles user authentication, profile management,
    favorites tracking, fines, and account status.
    
    Attributes:
        id (str): Unique user identifier.
        email (str): User's email address (unique).
        name (str): Full name.
        phone (str): Contact phone number.
        birthday (str): Date of birth.
        role (str): User role ('user', 'staff', 'admin').
        member_since (str): Registration date.
        is_locked (bool): Account lock status.
        fines (float): Outstanding fine amount.
        violations (int): Number of violations.
        favorites (List[str]): List of favorite book IDs.
        password (str): Hashed password (only loaded when needed).
    """
    
    def __init__(self, id: str, email: str, name: str, phone: str,
                 birthday: str, role: str, member_since: str,
                 is_locked: int, fines: float, violations: int,
                 favorites: str, password: Optional[str] = None,
                 total_fine: float = 0.0, **kwargs) -> None:
        """Initialize a User instance.
        
        Args:
            id: Unique identifier.
            email: Email address.
            name: Full name.
            phone: Phone number.
            birthday: Date of birth.
            role: User role.
            member_since: Registration date.
            is_locked: Lock status (0 or 1).
            fines: Fine amount.
            violations: Violation count.
            favorites: JSON string of favorite book IDs.
            password: Hashed password (optional).
            total_fine: Total unpaid fines (default: 0.0).
            **kwargs: Additional fields from database queries (ignored).
        """
        self.id = id
        self.email = email
        self.name = name
        self.phone = phone
        self.birthday = birthday
        self.role = role
        self.member_since = member_since
        self.is_locked = bool(is_locked)
        self.fines = float(fines)
        self.violations = int(violations)
        self.favorites = json.loads(favorites) if isinstance(favorites, str) else favorites
        self.password = password
        self.total_fine = float(total_fine)
    
    @staticmethod
    def get_by_id(user_id: str) -> Optional['User']:
        """Retrieve a user by their ID.
        
        Args:
            user_id: The unique identifier of the user.
            
        Returns:
            User, Staff, or Admin instance based on role. None if not found.
        """
        db = get_db()
        row = db.execute(
            'SELECT id, email, name, phone, birthday, role, member_since, '
            'is_locked, fines, violations, favorites FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()
        if row:
            row_dict = dict(row)
            # Return appropriate class based on role (lazy import)
            role = row_dict.get('role', 'user')
            if role == 'admin':
                Admin = _get_admin_class()
                return Admin(**row_dict)
            elif role == 'staff':
                Staff = _get_staff_class()
                return Staff(**row_dict)
            return User(**row_dict)
        return None
    
    @staticmethod
    def get_by_email(email: str) -> Optional['User']:
        """Retrieve a user by their email address.
        
        Args:
            email: The email address to search for.
            
        Returns:
            User, Staff, or Admin instance with password if found, None otherwise.
        """
        db = get_db()
        row = db.execute(
            'SELECT id, email, name, phone, birthday, role, member_since, '
            'is_locked, fines, violations, favorites, password FROM users WHERE email = ?',
            (email,)
        ).fetchone()
        if row:
            row_dict = dict(row)
            # Return appropriate class based on role (lazy import)
            role = row_dict.get('role', 'user')
            if role == 'admin':
                Admin = _get_admin_class()
                return Admin(**row_dict)
            elif role == 'staff':
                Staff = _get_staff_class()
                return Staff(**row_dict)
            return User(**row_dict)
        return None
    
    @staticmethod
    def create(email: str, password: str, name: str, phone: str,
               birthday: Optional[str] = None, role: str = 'user') -> Optional['User']:
        """Create a new user account.
        
        Args:
            email: Email address (must be unique).
            password: Plain text password (will be hashed).
            name: Full name.
            phone: Phone number.
            birthday: Date of birth (optional).
            role: User role (default: 'user').
            
        Returns:
            New User instance if successful, None if email exists.
        """
        import uuid
        db = get_db()
        
        # Check if email already exists
        if User.get_by_email(email):
            return None
        
        user_id = str(uuid.uuid4())
        hashed_password = generate_password_hash(password)
        member_since = datetime.now().strftime('%Y-%m-%d')
        
        try:
            db.execute('''
                INSERT INTO users (id, email, password, name, phone, birthday, role, 
                                 member_since, is_locked, fines, violations, favorites)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0.0, 0, '[]')
            ''', (user_id, email, hashed_password, name, phone, birthday, role, member_since))
            db.commit()
            
            return User.get_by_id(user_id)
        except Exception as e:
            print(f"Error creating user: {e}")
            return None
    
    def update(self, name: Optional[str] = None, phone: Optional[str] = None,
               birthday: Optional[str] = None) -> bool:
        """Update user profile information.
        
        Args:
            name: New name (optional).
            phone: New phone number (optional).
            birthday: New birthday (optional).
            
        Returns:
            True if update successful.
        """
        db = get_db()
        
        if name:
            self.name = name
        if phone:
            self.phone = phone
        if birthday:
            self.birthday = birthday
        
        db.execute('''
            UPDATE users SET name = ?, phone = ?, birthday = ?
            WHERE id = ?
        ''', (self.name, self.phone, self.birthday, self.id))
        db.commit()
        return True
    
    def check_password(self, password: str) -> bool:
        """Verify if the provided password is correct.
        
        Args:
            password: Plain text password to verify.
            
        Returns:
            True if password matches, False otherwise.
        """
        if not self.password:
            return False
        return check_password_hash(self.password, password)
    
    def add_favorite(self, book_id: str) -> bool:
        """Add a book to user's favorites list.
        
        Args:
            book_id: ID of the book to add.
            
        Returns:
            True if added, False if already in favorites.
        """
        if book_id not in self.favorites:
            self.favorites.append(book_id)
            db = get_db()
            db.execute(
                'UPDATE users SET favorites = ? WHERE id = ?',
                (json.dumps(self.favorites), self.id)
            )
            db.commit()
            return True
        return False
    
    def remove_favorite(self, book_id: str) -> bool:
        """Remove a book from user's favorites list.
        
        Args:
            book_id: ID of the book to remove.
            
        Returns:
            True if removed, False if not in favorites.
        """
        if book_id in self.favorites:
            self.favorites.remove(book_id)
            db = get_db()
            db.execute(
                'UPDATE users SET favorites = ? WHERE id = ?',
                (json.dumps(self.favorites), self.id)
            )
            db.commit()
            return True
        return False
    
    def add_fine(self, amount: float) -> None:
        """Add a fine amount to user's account.
        
        Args:
            amount: Fine amount to add.
        """
        self.fines += amount
        db = get_db()
        db.execute('UPDATE users SET fines = ? WHERE id = ?', (self.fines, self.id))
        db.commit()
    
    def pay_fine(self, amount: float) -> None:
        """Pay/reduce user's fine amount.
        
        Args:
            amount: Amount to pay (cannot go below 0).
        """
        self.fines = max(0, self.fines - amount)
        db = get_db()
        db.execute('UPDATE users SET fines = ? WHERE id = ?', (self.fines, self.id))
        db.commit()
    
    def add_fine_record(self) -> None:
        """Increment fine count by 1.
        
        Automatically locks account if fines exceed threshold.
        """
        self.violations += 1
        db = get_db()
        db.execute(
            'UPDATE users SET violations = ? WHERE id = ?',
            (self.violations, self.id)
        )
        db.commit()
        
        # Check if user should be locked
        from config.config import Config
        if self.violations >= Config.MAX_VIOLATIONS_BEFORE_LOCK:
            self.lock()
    
    # Alias for backward compatibility
    add_violation = add_fine_record
    
    def lock(self) -> None:
        """Lock the user account (prevent login and borrowing)."""
        self.is_locked = True
        db = get_db()
        db.execute('UPDATE users SET is_locked = 1 WHERE id = ?', (self.id,))
        db.commit()
    
    def unlock(self) -> None:
        """Unlock the user account (restore access)."""
        self.is_locked = False
        db = get_db()
        db.execute('UPDATE users SET is_locked = 0 WHERE id = ?', (self.id,))
        db.commit()
    
    @staticmethod
    def get_total_users() -> int:
        """Get total count of regular users.
        
        Returns:
            Number of users with 'user' role.
        """
        db = get_db()
        row = db.execute(
            'SELECT COUNT(*) as count FROM users WHERE role = "user"'
        ).fetchone()
        return row['count']
    
    @staticmethod
    def get_users_by_role(role: str) -> int:
        """Get count of users with specific role.
        
        Args:
            role: The role to count ('user', 'staff', 'admin').
            
        Returns:
            Number of users with specified role.
        """
        db = get_db()
        row = db.execute(
            'SELECT COUNT(*) as count FROM users WHERE role = ?',
            (role,)
        ).fetchone()
        return row['count']
    
    @staticmethod
    def get_all_users() -> List['User']:
        """Retrieve all users from database.
        
        Returns:
            List of User, Staff, or Admin instances based on role.
        """
        db = get_db()
        rows = db.execute(
            'SELECT id, email, name, phone, birthday, role, member_since, '
            'is_locked, fines, violations, favorites FROM users'
        ).fetchall()
        
        # Lazy import to avoid circular imports
        Staff = _get_staff_class()
        Admin = _get_admin_class()
        
        result = []
        for row in rows:
            row_dict = dict(row)
            role = row_dict.get('role', 'user')
            if role == 'admin':
                result.append(Admin(**row_dict))
            elif role == 'staff':
                result.append(Staff(**row_dict))
            else:
                result.append(User(**row_dict))
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary representation.
        
        Note: Does not include password for security.
        
        Returns:
            Dictionary containing all user attributes (except password).
        """
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'phone': self.phone,
            'birthday': self.birthday,
            'role': self.role,
            'member_since': self.member_since,
            'is_locked': self.is_locked,
            'fines': self.fines,
            'violations': self.violations,
            'favorites': self.favorites
        }
    
    # ==================== SERVICE METHODS (Merged from AuthService) ====================
    
    @staticmethod
    def login(email: str, password: str) -> Optional['User']:
        """Authenticate user with email and password.
        
        Args:
            email: User's email address.
            password: Plain text password to verify.
            
        Returns:
            User instance if authentication successful, None otherwise.
        """
        user = User.get_by_email(email)
        
        if not user:
            return None
        
        if user.is_locked:
            return None
        
        if user.check_password(password):
            return user
        
        return None
    
    @staticmethod
    def reset_password(email: str, new_password: str) -> bool:
        """Reset user password.
        
        Args:
            email: User's email address.
            new_password: New plain text password (will be hashed).
            
        Returns:
            True if password reset successful, False if user not found.
        """
        user = User.get_by_email(email)
        if user:
            hashed_password = generate_password_hash(new_password)
            db = get_db()
            db.execute(
                'UPDATE users SET password = ? WHERE id = ?',
                (hashed_password, user.id)
            )
            db.commit()
            return True
        return False
    
    def get_favorite_books(self) -> List:
        """Get user's favorite books.
        
        Returns:
            List of favorite Book instances.
        """
        from models.book import Book
        favorites = []
        for book_id in self.favorites:
            book = Book.get_by_id(book_id)
            if book:
                favorites.append(book)
        return favorites
    
    # ==================== PERMISSION CHECK METHODS ====================
    
    def is_staff(self) -> bool:
        """Check if user has staff privileges.
        
        Returns:
            True if user is staff or admin.
        """
        return self.role in ('staff', 'admin')
    
    def is_admin(self) -> bool:
        """Check if user has admin privileges.
        
        Returns:
            True if user is admin.
        """
        return self.role == 'admin'
    
    def can_manage_borrows(self) -> bool:
        """Check if user can manage borrow requests.
        
        Returns:
            True if staff or admin.
        """
        return self.is_staff()
    
    def can_manage_users(self) -> bool:
        """Check if user can manage other users.
        
        Returns:
            True if admin only.
        """
        return self.is_admin()
    
    def can_manage_books(self) -> bool:
        """Check if user can add/edit/delete books.
        
        Returns:
            True if admin only.
        """
        return self.is_admin()
    
    def can_send_notifications(self) -> bool:
        """Check if user can send system notifications.
        
        Returns:
            True if staff or admin.
        """
        return self.is_staff()
    
    def can_view_system_logs(self) -> bool:
        """Check if user can view system logs.
        
        Returns:
            True if admin only.
        """
        return self.is_admin()


# ==================== HELPER FUNCTIONS ====================

def _get_staff_class():
    """Lazy import Staff class to avoid circular imports."""
    from models.staff import Staff
    return Staff


def _get_admin_class():
    """Lazy import Admin class to avoid circular imports."""
    from models.admin import Admin
    return Admin


def get_user_by_role(row_data: dict) -> 'User':
    """Factory function to create appropriate User subclass based on role.
    
    Args:
        row_data: Dictionary containing user data from database.
        
    Returns:
        User, Staff, or Admin instance based on role.
    """
    role = row_data.get('role', 'user')
    
    if role == 'admin':
        Admin = _get_admin_class()
        return Admin(**row_data)
    elif role == 'staff':
        Staff = _get_staff_class()
        return Staff(**row_data)
    else:
        return User(**row_data)
