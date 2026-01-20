"""User model module.

Acts as a Factory for User/Staff/Admin and handles payment logic.
"""
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from models.book import Book
from werkzeug.security import check_password_hash, generate_password_hash

from models.database import get_db
from models.guest import Guest  # Import chuẩn, đã loại bỏ block try/except dự phòng

class User:
    @staticmethod
    def get_users_with_debt():
        """Get list of users who have outstanding fines."""
        db = get_db()
        rows = db.execute(
            'SELECT * FROM users WHERE fines > 0 ORDER BY fines DESC'
        ).fetchall()
        return [get_user_by_role(dict(r)) for r in rows]

    def __init__(self, id, email, name, role, fines, favorites, **kwargs):
        self.id = id
        self.email = email
        self.name = name
        self.role = role
        # Xử lý an toàn cho fines
        self.fines = float(fines) if fines is not None else 0.0
        # Xử lý an toàn cho favorites
        if isinstance(favorites, str):
            try:
                self.favorites = json.loads(favorites)
            except:
                self.favorites = []
        else:
            self.favorites = favorites if favorites else []
            
        # Các thuộc tính khác từ kwargs
        self.phone = kwargs.get('phone')
        self.birthday = kwargs.get('birthday')
        self.member_since = kwargs.get('member_since')
        self.is_locked = bool(kwargs.get('is_locked', 0))
        self.password = kwargs.get('password')
        self.violations = int(kwargs.get('violations', 0))

    @staticmethod
    def get_user_or_guest(user_id: Optional[str]) -> 'User':
        """Get User object or Guest object."""
        if not user_id:
            return Guest()
        user = User.get_by_id(user_id)
        return user if user else Guest()

    @staticmethod
    def get_by_id(user_id: str) -> Optional['User']:
        """Factory Method: Get User, Staff, or Admin instance by ID."""
        db = get_db()
        row = db.execute(
            'SELECT * FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()
        if not row:
            return None
        return get_user_by_role(dict(row))

    @staticmethod
    def get_by_email(email: str) -> Optional['User']:
        """Get user by email and return correct class (User/Staff/Admin)."""
        db = get_db()
        row = db.execute(
            'SELECT * FROM users WHERE email = ?',
            (email,)
        ).fetchone()
        if not row:
            return None
        return get_user_by_role(dict(row))

    @staticmethod
    def login(email: str, password: str) -> Optional['User']:
        """Login user with email and password."""
        user = User.get_by_email(email)
        if user and not user.is_locked and user.check_password(password):
            return user
        return None

    @staticmethod
    def create(email: str, password: str, name: str, phone: str,
               birthday: Optional[str] = None, role: str = 'user') -> Optional['User']:
        """Create new user."""
        if User.get_by_email(email):
            return None

        user_id = str(uuid.uuid4())
        hashed_password = generate_password_hash(password)
        member_since = datetime.now().strftime('%Y-%m-%d')

        try:
            db = get_db()
            db.execute('''
                INSERT INTO users (id, email, password, name, phone, birthday, role,
                                 member_since, is_locked, fines, violations, favorites)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0.0, 0, '[]')
            ''', (user_id, email, hashed_password, name, phone, birthday, role,
                  member_since))
            db.commit()

            return User.get_by_id(user_id)
        except Exception as e:
            print(f"Error creating user: {e}")
            return None

    def update(self, name=None, phone=None, birthday=None) -> Tuple[bool, str]:
        """Update user profile information."""
        db = get_db()
        if name:
            self.name = name
        if phone:
            self.phone = phone
        if birthday:
            self.birthday = birthday

        try:
            db.execute(
                'UPDATE users SET name=?, phone=?, birthday=? WHERE id=?',
                (self.name, self.phone, self.birthday, self.id)
            )
            db.commit()
            return True, "Profile updated successfully"
        except Exception as e:
            return False, f"Failed to update profile: {str(e)}"

    def check_password(self, password: str) -> bool:
        """Check if provided password matches user password."""
        if not self.password:
            return False
        return check_password_hash(self.password, password)

    def pay_fine(self, amount: float) -> Tuple[bool, str]:
        """Pay fine amount and update violation records.
        
        ✅ FIXED: Now updates violations_history status to 'paid'
        """
        if amount <= 0 or self.fines <= 0:
            return False, "No fines to pay or invalid amount"

        pay_amount = min(self.fines, float(amount))
        self.fines -= pay_amount

        db = get_db()
        try:
            # 1. Update user fine balance
            db.execute(
                'UPDATE users SET fines = ? WHERE id = ?',
                (self.fines, self.id)
            )

            # 2. ✅ FIXED: Update violations_history to mark as paid
            # Update violation records associated with this user to 'paid' status
            db.execute(
                "UPDATE violations_history SET payment_status = 'paid' "
                "WHERE user_id = ? AND payment_status = 'unpaid'",
                (self.id,)
            )

            # 3. Unlock account if debt cleared
            if self.fines == 0 and self.is_locked:
                self.unlock()

            db.commit()
            return True, f"Paid {pay_amount:,.0f} VND. Remaining: {self.fines:,.0f} VND"
        except Exception as e:
            db.rollback()
            return False, f"Payment failed: {str(e)}"

    def lock(self) -> None:
        """Lock user account."""
        self.is_locked = True
        db = get_db()
        db.execute('UPDATE users SET is_locked = 1 WHERE id = ?', (self.id,))
        db.commit()

    def unlock(self) -> None:
        """Unlock user account."""
        self.is_locked = False
        db = get_db()
        db.execute('UPDATE users SET is_locked = 0 WHERE id = ?', (self.id,))
        db.commit()

    def reset_password(self, new_password: str) -> Tuple[bool, str]:
        """Reset user password."""
        from werkzeug.security import generate_password_hash

        try:
            db = get_db()
            hashed_password = generate_password_hash(new_password)
            db.execute(
                'UPDATE users SET password = ? WHERE id = ?',
                (hashed_password, self.id)
            )
            db.commit()
            return True, "Password reset successful"
        except Exception as e:
            return False, f"Password reset failed: {str(e)}"

    def add_fine(self, amount: float) -> None:
        """Add fine amount to user account."""
        self.fines += float(amount)
        db = get_db()
        db.execute('UPDATE users SET fines = ? WHERE id = ?', (self.fines, self.id))
        db.commit()

    def add_violation(self) -> None:
        """Increment violation count for user."""
        self.violations += 1
        db = get_db()
        db.execute(
            'UPDATE users SET violations = ? WHERE id = ?',
            (self.violations, self.id)
        )
        db.commit()

    def can_manage_borrows(self) -> bool:
        """Check if user can manage borrows (staff or admin)."""
        return self.is_staff()

    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role == 'admin'

    def is_staff(self) -> bool:
        """Check if user is staff or admin."""
        return self.role in ['staff', 'admin']
    
    def get_favorite_books(self) -> List['Book']:
        """Get list of favorite books."""
        from models.book import Book
        return [Book.get_by_id(bid) for bid in self.favorites
                if Book.get_by_id(bid)]

    def add_favorite(self, book_id: str) -> bool:
        """Add book to favorites."""
        if book_id not in self.favorites:
            self.favorites.append(book_id)
            self._save_favorites()
            return True
        return False

    def remove_favorite(self, book_id: str) -> bool:
        """Remove book from favorites."""
        if book_id in self.favorites:
            self.favorites.remove(book_id)
            self._save_favorites()
            return True
        return False

    def _save_favorites(self) -> None:
        """Save favorites to database."""
        db = get_db()
        db.execute(
            'UPDATE users SET favorites = ? WHERE id = ?',
            (json.dumps(self.favorites), self.id)
        )
        db.commit()

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'fines': self.fines,
            'is_locked': self.is_locked
        }

    @staticmethod
    def get_total_users() -> int:
        """Get total count of regular users."""
        db = get_db()
        return db.execute(
            'SELECT COUNT(*) as c FROM users WHERE role="user"'
        ).fetchone()['c']

    @staticmethod
    def get_users_by_role(role: str) -> int:
        """Get count of users by role."""
        db = get_db()
        return db.execute(
            'SELECT COUNT(*) as c FROM users WHERE role=?',
            (role,)
        ).fetchone()['c']

    @staticmethod
    def get_all_users() -> List['User']:
        """Get all users (for API/Admin)."""
        db = get_db()
        rows = db.execute('SELECT * FROM users').fetchall()
        return [get_user_by_role(dict(r)) for r in rows]

    def get_book_interaction_status(self, book_id: str, book_obj=None) -> dict:
        """
        Kiểm tra toàn bộ trạng thái tương tác giữa User và Book.
        Trả về dict chứa tất cả flags cần thiết cho template.
        """
        from models.borrow import Borrow
        from models.review import Review
        # from models.reservation import Reservation (Not used directly here but implied)

        status = {
            'is_favorite': book_id in self.favorites,
            'can_borrow': False,
            'can_reserve': False,
            'is_borrowed': False,
            'is_reserved': False,
            'can_review': False,
            'user_review': None
        }

        active_borrows = Borrow.get_active_borrows(self.id)
        reserved_books = Borrow.get_user_reserved_books(self.id)

        status['is_borrowed'] = any(b.book_id == book_id for b in active_borrows)
        status['is_reserved'] = any(r.book_id == book_id for r in reserved_books)

        if not status['is_borrowed'] and not status['is_reserved'] and book_obj:
            if book_obj.available_copies > 0:
                status['can_borrow'] = True
            else:
                status['can_reserve'] = True

        reviews = Review.get_by_book(book_id)
        status['can_review'] = not any(r.user_id == self.id for r in reviews)

        if not status['can_review']:
            my_reviews = [r for r in reviews if r.user_id == self.id]
            # Convert object to dict for template if needed, or keep object
            # Original code expected dict from 'get_book_reviews_with_details'
            # Here we provide the object, template should handle 'r.comment' etc.
            status['user_review'] = my_reviews[0].to_dict() if my_reviews else None

        return status

# ==================== HELPER FUNCTIONS (Factory Logic) ====================

def _get_staff_class():
    from models.staff import Staff
    return Staff

def _get_admin_class():
    from models.admin import Admin
    return Admin

def get_user_by_role(row_data: dict) -> User:
    """Factory function to create correct User subclass."""
    role = row_data.get('role', 'user')

    if role == 'admin':
        Admin = _get_admin_class()
        return Admin(**row_data)
    elif role == 'staff':
        Staff = _get_staff_class()
        return Staff(**row_data)
    else:
        return User(**row_data)