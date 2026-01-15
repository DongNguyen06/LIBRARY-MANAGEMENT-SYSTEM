"""
Fine model module.
Handles fine logic and backward compatibility.
"""
import uuid
from datetime import datetime
# Không import get_db ở đây để tránh lỗi circular import, sẽ import bên trong hàm

class Fine:
    def __init__(self, id, user_id, amount, reason, date, status='unpaid'):
        self.id = id
        self.user_id = user_id
        self.amount = amount
        self.reason = reason
        self.date = date
        self.status = status

    @staticmethod
    def create(user_id, amount, reason, borrow_id=None):
        """Tạo khoản phạt mới và ghi vào DB"""
        from models.database import get_db
        
        if amount <= 0:
            return None
            
        db = get_db()
        fine_id = str(uuid.uuid4())
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Ghi vào bảng violations_history
            # Lưu ý: Cần đảm bảo bảng violations_history đã tồn tại trong DB
            db.execute('''
                INSERT INTO violations_history (id, user_id, borrow_id, violation_type, 
                                            description, fine_amount, payment_status, violation_date)
                VALUES (?, ?, ?, 'fine', ?, ?, 'unpaid', ?)
            ''', (fine_id, user_id, borrow_id, reason, amount, date))
            
            # Cộng dồn nợ vào bảng users
            db.execute('UPDATE users SET fines = fines + ? WHERE id = ?', (amount, user_id))
            db.commit()
            
            return fine_id
        except Exception as e:
            print(f"Error creating fine: {e}")
            return None