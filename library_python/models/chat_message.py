"""Chat message model for real-time messaging.

This module handles creating, retrieving, and managing
chat messages between users and staff.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from models.database import get_db


class ChatMessage:
    """Represents a chat message between users and staff."""

    def __init__(self, id: str, sender_id: str, receiver_id: str,
                 message: str, timestamp: str, is_read: int) -> None:
        """Initialize a ChatMessage instance."""
        self.id = id
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.message = message
        self.timestamp = timestamp
        self.is_read = bool(is_read)

    @staticmethod
    def create(sender_id: str, receiver_id: str,
               message: str) -> Optional['ChatMessage']:
        """Create a new chat message."""
        db = get_db()
        message_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        db.execute('''
            INSERT INTO chat_messages (id, sender_id, receiver_id, message, timestamp, is_read)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (message_id, sender_id, receiver_id, message, timestamp))
        db.commit()

        return ChatMessage.get_by_id(message_id)

    @staticmethod
    def get_by_id(message_id: str) -> Optional['ChatMessage']:
        """Get message by ID."""
        db = get_db()
        row = db.execute(
            'SELECT * FROM chat_messages WHERE id = ?',
            (message_id,)
        ).fetchone()
        if row:
            return ChatMessage(**dict(row))
        return None

    @staticmethod
    def get_conversation(user1_id: str, user2_id: str,
                         limit: int = 50) -> List['ChatMessage']:
        """Get conversation between two users."""
        db = get_db()
        rows = db.execute('''
            SELECT * FROM chat_messages 
            WHERE (sender_id = ? AND receiver_id = ?) 
               OR (sender_id = ? AND receiver_id = ?)
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user1_id, user2_id, user2_id, user1_id, limit)).fetchall()

        messages = [ChatMessage(**dict(row)) for row in rows]
        return list(reversed(messages))  # Oldest first

    @staticmethod
    def get_unread_count(user_id: str) -> int:
        """Get count of unread messages for a user."""
        db = get_db()
        row = db.execute('''
            SELECT COUNT(*) as count FROM chat_messages 
            WHERE receiver_id = ? AND is_read = 0
        ''', (user_id,)).fetchone()
        return row['count']

    @staticmethod
    def mark_as_read(user_id: str, sender_id: str) -> None:
        """Mark all messages from sender to user as read."""
        db = get_db()
        db.execute('''
            UPDATE chat_messages 
            SET is_read = 1 
            WHERE receiver_id = ? AND sender_id = ?
        ''', (user_id, sender_id))
        db.commit()

    @staticmethod
    def get_recent_conversations(user_id: str) -> List[dict]:
        """Get list of recent conversations for a user."""
        db = get_db()

        rows = db.execute('''
            SELECT DISTINCT 
                CASE 
                    WHEN sender_id = ? THEN receiver_id
                    ELSE sender_id
                END as partner_id,
                MAX(timestamp) as last_message_time
            FROM chat_messages
            WHERE sender_id = ? OR receiver_id = ?
            GROUP BY partner_id
            ORDER BY last_message_time DESC
        ''', (user_id, user_id, user_id)).fetchall()

        conversations = []
        for row in rows:
            partner_id = row['partner_id']
            last_msg = db.execute('''
                SELECT * FROM chat_messages
                WHERE (sender_id = ? AND receiver_id = ?) 
                   OR (sender_id = ? AND receiver_id = ?)
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (user_id, partner_id, partner_id, user_id)).fetchone()

            unread = db.execute('''
                SELECT COUNT(*) as count FROM chat_messages
                WHERE sender_id = ? AND receiver_id = ? AND is_read = 0
            ''', (partner_id, user_id)).fetchone()

            conversations.append({
                'partner_id': partner_id,
                'last_message': last_msg['message'] if last_msg else '',
                'last_time': last_msg['timestamp'] if last_msg else '',
                'unread_count': unread['count']
            })

        return conversations

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'message': self.message,
            'timestamp': self.timestamp,
            'is_read': self.is_read
        }

    # ==================== SERVICE METHODS ====================

    @staticmethod
    def send_message(sender_id: str, receiver_id: str,
                     message: str) -> tuple:
        """Send a chat message without checking online status."""
        from models.user import User
        
        if not message or not message.strip():
            return None, "Message cannot be empty"

        sender = User.get_by_id(sender_id)
        receiver = User.get_by_id(receiver_id)

        if not sender or not receiver:
            return None, "Invalid sender or receiver"

        # Create message - always save to DB
        chat_message = ChatMessage.create(sender_id, receiver_id, message.strip())
        
        if chat_message:
            # ĐÃ XÓA: Logic check online_users
            return chat_message, "Message sent successfully"
        
        return None, "Failed to save message"

    @staticmethod
    def get_unread_messages(user_id: str) -> list:
        """Get unread messages for a user."""
        db = get_db()
        rows = db.execute('''
            SELECT * FROM chat_messages 
            WHERE receiver_id = ? AND is_read = 0
            ORDER BY timestamp DESC
        ''', (user_id,)).fetchall()
        
        messages = [ChatMessage(**dict(row)) for row in rows]
        return messages

    @staticmethod
    def get_staff_availability() -> dict:
        """Get staff list without online/offline status distinction."""
        db = get_db()
        
        # Get all staff members
        staff_list = db.execute('''
            SELECT id, name FROM users 
            WHERE role IN ('staff', 'admin')
            ORDER BY name
        ''').fetchall()
        
        available_staff = []
        
        # Tất cả staff đều được đưa vào danh sách available (chỉ còn là danh sách nhân viên)
        for staff in staff_list:
            available_staff.append({
                'id': staff['id'],
                'name': staff['name'],
                # Có thể bỏ field status hoặc để mặc định nếu frontend cũ cần
                'status': 'available' 
            })
        
        return {
            'available': available_staff,
            'offline': [], # Danh sách rỗng
            'staff_online': True # Luôn True để hiển thị danh sách
        }

    @staticmethod
    def get_recent_conversations_with_details(user_id: str) -> List[dict]:
        """Get recent conversations with user details."""
        from models.user import User

        conversations = ChatMessage.get_recent_conversations(user_id)

        for conv in conversations:
            partner = User.get_by_id(conv['partner_id'])
            if partner:
                conv['partner_name'] = partner.name
                conv['partner_email'] = partner.email
                conv['partner_role'] = partner.role

        return conversations

    @staticmethod
    def get_available_staff() -> List[dict]:
        """Get list of staff/admin members available for chat."""
        db = get_db()
        rows = db.execute('''
            SELECT id, name, email FROM users 
            WHERE role IN ('staff', 'admin')
            ORDER BY name
        ''').fetchall()

        return [
            {'id': row['id'], 'name': row['name'], 'email': row['email']}
            for row in rows
        ]