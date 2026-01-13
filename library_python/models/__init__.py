"""
Models package

Class Hierarchy:
    User (base) - Regular library members (user.py)
    ├── Staff - Library staff with borrow management permissions (staff.py)
    └── Admin - System administrators with full access (admin.py)
"""
from models.user import User, get_user_by_role
from models.staff import Staff
from models.admin import Admin
from models.book import Book, Review
from models.borrow import Borrow
from models.fine import Fine, Violation  # Violation is alias for backward compatibility
from models.database import init_db, get_db, close_db

__all__ = [
    'User', 'Staff', 'Admin', 'get_user_by_role',
    'Book', 'Review', 'Borrow', 'Fine', 'Violation',
    'init_db', 'get_db', 'close_db'
]
