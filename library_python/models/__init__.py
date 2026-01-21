"""
Models package

Class Hierarchy:
    User (base) - Regular library members (user.py)
    ├── Staff - Library staff with borrow management permissions (staff.py)
    └── Admin - System administrators with full access (admin.py)
"""
from models.user import User, get_user_by_role
from models.guest import Guest  # <--- THÊM DÒNG NÀY
from models.staff import Staff
from models.admin import Admin
from models.book import Book        # <--- Chỉ import Book từ models.book
from models.review import Review    # <--- Import Review từ file mới models.review
from models.borrow import Borrow
from models.fine import Fine        # Remove Violation alias
from models.chat_message import ChatMessage
from models.notification import Notification
from models.database import init_db, get_db, close_db

__all__ = [
    'User', 'Guest', 'Staff', 'Admin', 'get_user_by_role',
    'Book', 'Review', 'Borrow', 'Fine',
    'ChatMessage', 'Notification',
    'init_db', 'get_db', 'close_db'
]