"""Staff model.

Encapsulates business logic for staff operations.
"""
from typing import Dict, Tuple

from models.book import Book
from models.borrow import Borrow
from models.database import get_db
from models.fine import Fine
from models.system_log import SystemLog
from models.user import User

class Staff(User):
    
    def approve_borrow_request(self, borrow_id: str) -> Tuple[bool, str]:
        """Approve borrow request (pickup).

        Args:
            borrow_id: ID of borrow request.

        Returns:
            Tuple of (success, message).
        """
        borrow = Borrow.get_by_id(borrow_id)
        if not borrow:
            return False, "Request not found"

        if borrow.status == 'pending_pickup':
            success, message = borrow.approve_pickup()
            if success:
                SystemLog.add(
                    'Approve Borrow',
                    f'Staff {self.name} approved pickup for borrow {borrow_id}',
                    'info',
                    self.id
                )
            return success, message
        return False, "Invalid status for approval"

    def reject_borrow_request(self, borrow_id: str) -> Tuple[bool, str]:
        """Reject borrow request.

        Args:
            borrow_id: ID of borrow request.

        Returns:
            Tuple of (success, message).
        """
        borrow = Borrow.get_by_id(borrow_id)
        if not borrow:
            return False, "Request not found"

        if borrow.status == 'pending_pickup':
            success, message = borrow.cancel()
            if success:
                SystemLog.add(
                    'Reject Borrow',
                    f'Staff {self.name} rejected borrow {borrow_id}',
                    'info',
                    self.id
                )
            return success, message
        return False, "Only pending requests can be rejected"

    def process_direct_borrow(self, user_email: str,
                              book_isbn: str) -> Tuple[bool, str]:
        """Process direct borrow at counter.

        Args:
            user_email: Email of user borrowing.
            book_isbn: ISBN of book to borrow.

        Returns:
            Tuple of (success, message).
        """
        from models.user import User as UserModel

        target_user = UserModel.get_by_email(user_email)
        if not target_user:
            return False, "User not found"

        book = Book.get_by_isbn(book_isbn)
        if not book:
            return False, "Book not found"

        if book.available_copies <= 0:
            return False, "Book is not available"

        # Create borrow record
        borrow, msg = Borrow.create(target_user.id, book.id)
        if borrow:
            # Approve immediately (user is at counter)
            borrow.approve_pickup()

            SystemLog.add(
                'Direct Borrow',
                f'Staff {self.name} processed direct borrow of "{book.title}" '
                f'to {target_user.name}',
                'info',
                self.id
            )
            return True, f"Book borrowed successfully to {target_user.name}"

        return False, msg

    def process_book_return(self, isbn: str, condition: str,
                           book_value: float,
                           fine_paid_now: bool = False) -> Tuple[bool, str]:
        """Process book return with fee calculation.

        Args:
            isbn: ISBN of book being returned.
            condition: Book condition.
            book_value: Original book value.
            fine_paid_now: Whether fine is paid immediately.

        Returns:
            Tuple of (success, message).
        """
        book = Book.get_by_isbn(isbn)
        if not book:
            return False, "Book not found by ISBN"

        # Find active borrow record
        db = get_db()
        row = db.execute(
            "SELECT id FROM borrows WHERE book_id = ? AND status = 'borrowed'",
            (book.id,)
        ).fetchone()
        if not row:
            return False, "No active borrow record found for this book"

        borrow = Borrow.get_by_id(row['id'])

        # Return book (Borrow model calculates fees and creates Fine)
        success, message = borrow.return_book(condition, book_value)

        if success:
            # If fine paid immediately
            if fine_paid_now:
                from models.user import User as UserModel
                target_user = UserModel.get_by_id(borrow.user_id)
                if target_user:
                    total_fee = (getattr(borrow, 'late_fee', 0) +
                               getattr(borrow, 'damage_fee', 0))
                    if total_fee > 0:
                        target_user.pay_fine(total_fee)
                        message += " (Fine paid immediately)"

            SystemLog.add(
                'Return Processed',
                f'Staff {self.name} processed return for "{book.title}". '
                f'Condition: {condition}',
                'info',
                self.id
            )
            return True, message

        return False, message

    def update_book_info(self, book_id: str, title: str, author: str,
                        description: str, total: int,
                        available: int) -> Tuple[bool, str]:
        """Update book information.

        Args:
            book_id: ID of book to update.
            title: New title.
            author: New author.
            description: New description.
            total: Total copies.
            available: Available copies.

        Returns:
            Tuple of (success, message).
        """
        if available > total:
            return False, "Available copies cannot exceed total copies"

        book = Book.get_by_id(book_id)
        if not book:
            return False, "Book not found"

        success, message = book.update_fields(
            title=title,
            author=author,
            description=description,
            total_copies=total,
            available_copies=available
        )

        if success:
            SystemLog.add(
                'Book Update',
                f'Staff {self.name} updated book {title}',
                'info',
                self.id
            )

        return success, message

    def get_stats(self) -> Dict[str, any]:
        """Get dashboard statistics for staff.

        Returns:
            Dictionary containing dashboard statistics.
        """
        db = get_db()

        # Get total debt from users table
        total_debt_row = db.execute(
            'SELECT SUM(fines) as total FROM users'
        ).fetchone()
        total_debt = total_debt_row['total'] or 0.0

        stats = {
            'borrowed': Borrow.get_active_borrows_count(),
            'overdue': Borrow.get_overdue_count(),
            'fines': total_debt,
            'members': User.get_total_users(),
            'unread_messages': 0
        }

        return stats