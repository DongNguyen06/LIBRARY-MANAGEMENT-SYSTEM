"""Staff dashboard and management routes.

This module handles staff-specific operations including borrow approval,
book returns, and inventory management.
"""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models.book import Book
from models.borrow import Borrow
from models.reservation import Reservation
from models.staff import Staff
from models.user import User
from utils.decorators import login_required, role_required

# Create staff blueprint
staff_bp = Blueprint('staff', __name__)


@staff_bp.route('/dashboard')
@login_required
@role_required('staff')
def dashboard():
    """Display staff dashboard with pending requests and statistics.
    
    Returns:
        Rendered staff dashboard template.
    """
    staff = Staff.get_by_id(session['user_id'])
    
    return render_template(
        'pages/staff/dashboard.html',
        pending_borrows=Borrow.get_user_borrows_by_status('pending_pickup'),
        borrowed_books=Borrow.get_user_borrows_by_status('borrowed'),
        overdue_books=Borrow.get_overdue_borrows(),
        all_books=Book.get_all(),
        all_reservations=Reservation.get_all(),
        popular_books=Book.get_most_borrowed(limit=10),
        stats=staff.get_stats(),
        users_with_debt=User.get_users_with_debt()
    )


@staff_bp.route('/approve/<borrow_id>', methods=['POST'])
@login_required
@role_required('staff')
def approve_borrow(borrow_id: str):
    """Approve a pending borrow request.
    
    Args:
        borrow_id: Unique identifier of the borrow request.
    
    Returns:
        Redirect to staff dashboard with status message.
    """
    staff = Staff.get_by_id(session['user_id'])
    success, message = staff.approve_borrow_request(borrow_id)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff.dashboard'))


@staff_bp.route('/reject/<borrow_id>', methods=['POST'])
@login_required
@role_required('staff')
def reject_borrow(borrow_id: str):
    """Reject a pending borrow request.
    
    Args:
        borrow_id: Unique identifier of the borrow request.
    
    Returns:
        Redirect to staff dashboard with status message.
    """
    staff = Staff.get_by_id(session['user_id'])
    success, message = staff.reject_borrow_request(borrow_id)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff.dashboard'))


@staff_bp.route('/process-borrow', methods=['POST'])
@login_required
@role_required('staff')
def process_borrow():
    """Process a direct borrow at the counter.
    
    Form data:
        user_email: Email of the user borrowing the book.
        book_isbn: ISBN of the book to borrow.
    
    Returns:
        Redirect to staff dashboard with status message.
    """
    staff = Staff.get_by_id(session['user_id'])
    user_email = request.form.get('user_email', '').strip()
    book_isbn = request.form.get('book_isbn', '').strip()
    
    success, message = staff.process_direct_borrow(user_email, book_isbn)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff.dashboard'))


@staff_bp.route('/process-return', methods=['POST'])
@login_required
@role_required('staff')
def process_return():
    """Process a book return with condition assessment.
    
    Form data:
        identifier: Book ISBN or borrow ID.
        condition: Book condition (good, minor_damage, major_damage, lost).
        book_value: Original book value for damage calculation.
        fine_paid: Whether fine was paid immediately (checkbox).
    
    Returns:
        Redirect to staff dashboard with status message.
    """
    staff = Staff.get_by_id(session['user_id'])
    
    identifier = request.form.get('identifier', '').strip()
    condition = request.form.get('condition', 'good')
    book_value = float(request.form.get('book_value', 0))
    fine_paid = request.form.get('fine_paid') == 'on'
    
    success, message = staff.process_book_return(
        identifier,
        condition,
        book_value,
        fine_paid
    )
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff.dashboard'))


@staff_bp.route('/book/edit', methods=['POST'])
@login_required
@role_required('staff')
def edit_book():
    """Update book information.
    
    Form data:
        book_id: Book identifier.
        title: Updated book title.
        author: Updated author name.
        description: Updated book description.
        total_copies: Total number of copies.
        available_copies: Currently available copies.
    
    Returns:
        Redirect to staff dashboard with status message.
    """
    staff = Staff.get_by_id(session['user_id'])
    
    book_id = request.form.get('book_id')
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    description = request.form.get('description', '').strip()
    total_copies = int(request.form.get('total_copies', 1))
    available_copies = int(request.form.get('available_copies', 0))
    
    success, message = staff.update_book_info(
        book_id,
        title,
        author,
        description,
        total_copies,
        available_copies
    )
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff.dashboard'))


@staff_bp.route('/send-notifications')
@login_required
@role_required('staff')
def send_notifications():
    """Display notification sending page for staff.
    
    Returns:
        Rendered notification sending template.
    """
    return render_template('pages/staff/send_notifications.html')