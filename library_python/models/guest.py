"""
Guest model for unauthenticated users.
Implements Null Object Pattern with Falsy evaluation.
"""

class Guest:
    def __init__(self):
        self.id = None
        self.name = "Guest"
        self.email = None
        self.role = "guest"
        self.fines = 0.0
        self.favorites = []

    # --- Các phương thức kiểm tra quyền ---
    def is_staff(self):
        return False
        
    def is_admin(self):
        return False
    
    # Hỗ trợ các thuộc tính chuẩn của Flask-Login (nếu template cần)
    @property
    def is_authenticated(self):
        return False
    
    @property
    def is_active(self):
        return False
    
    @property
    def is_anonymous(self):
        return True
    
    def get_id(self):
        return None
        
    def can_borrow(self):
        return False
    
    def pay_fine(self, amount):
        return False
        
    def to_dict(self):
        return {
            'id': None,
            'name': 'Guest',
            'role': 'guest'
        }

    # === MAGIC METHOD QUAN TRỌNG NHẤT ===
    def __bool__(self):
        """
        Giúp đối tượng Guest trả về False khi kiểm tra trong if.
        Ví dụ: {% if current_user %} sẽ trả về False.
        Điều này giúp giao diện hiển thị nút Login/Register thay vì Logout.
        """
        return False
    
    # Dành cho Python 2 (đề phòng)
    def __nonzero__(self):
        return False