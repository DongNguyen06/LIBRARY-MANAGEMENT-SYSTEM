from flask import Blueprint, flash, redirect, render_template, request, session, url_for, g
from models.borrow import Borrow
from models.reservation import Reservation
from models.user import User
from models.book import Book
from utils.decorators import login_required, role_required

# Create user blueprint
user_bp = Blueprint('user', __name__, url_prefix='/user')


@user_bp.route('/dashboard')
@login_required
@role_required('user')
def dashboard():
    """Display user dashboard with borrowing overview.
    
    Returns:
        Rendered dashboard template.
    """
    user = User.get_by_id(session['user_id'])
    
    return render_template(
        'pages/user/dashboard.html',
        borrowed_books=Borrow.get_user_borrowed_books(user.id),
        reserved_books=Borrow.get_user_reserved_books(user.id),
        overdue_books=Borrow.get_user_overdue_books(user.id),
        upcoming_due=Borrow.get_upcoming_due_books(user.id, days=3)
    )


@user_bp.route('/pay-fine', methods=['POST'])
@login_required
@role_required('user')
def pay_fine():
    """Process fine payment for current user.
    
    Returns:
        Redirect to dashboard with status message.
    """
    user = User.get_by_id(session['user_id'])
    success, message = user.pay_fine(user.fines)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('user.dashboard'))


@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Display and update user profile.
    
    GET: Show profile form.
    POST: Update profile information.
    
    Returns:
        Rendered profile template.
    """
    user = User.get_by_id(session['user_id'])
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        birthday = request.form.get('birthday')
        
        success, message = user.update(name, phone, birthday)
        flash(message, 'success' if success else 'error')
        
    return render_template('pages/user/profile.html', user=user)


@user_bp.route('/borrowed-books')
@login_required
@role_required('user')
def borrowed_books():
    """Display list of borrowed books.
    
    Returns:
        Rendered borrowed books template.
    """
    user = User.get_by_id(session['user_id'])
    borrowed = Borrow.get_user_borrowed_books(user.id)
    
    return render_template(
        'pages/user/borrowed_books.html',
        borrowed_books=borrowed
    )


@user_bp.route('/reservations')
@login_required
@role_required('user')
def reservations():
    """Display list of book reservations.
    
    Returns:
        Rendered reservations template.
    """
    user = User.get_by_id(session['user_id'])
    user_reservations = Reservation.get_user_reservations(user.id)
    
    return render_template(
        'pages/user/reservations.html',
        reservations=user_reservations
    )


@user_bp.route('/favorites')
@login_required
@role_required('user')
def favorites():
    """Display list of favorite books.
    
    Returns:
        Rendered favorites template.
    """
    user = User.get_by_id(session['user_id'])
    favorite_books = user.get_favorite_books()
    
    return render_template(
        'pages/user/favorites.html',
        favorite_books=favorite_books
    )


@user_bp.route('/notifications')
@login_required
@role_required('user')
def notifications():
    """Display user notifications.
    
    Returns:
        Rendered notifications template.
    """
    return render_template('pages/user/notifications.html')


@user_bp.route('/borrow/<book_id>', methods=['POST'])
@login_required
def borrow_book(book_id):
    """Handle book borrowing request from User Dashboard/Reservation page.
    
    This route now supports PRIORITY CLAIMING for reservations.
    If the user has a 'ready' reservation, Borrow.create will detect it
    and allow borrowing even if available_copies is 0.
    """
    # Gọi hàm create (đã chứa logic Hidden Inventory)
    borrow, message = Borrow.create(g.user.id, book_id)
    
    if borrow:
        flash(message, 'success')
        # Nếu đang ở trang reservations thì reload lại trang đó
        if 'reservations' in request.referrer:
            return redirect(url_for('user.reservations'))
        return redirect(url_for('user.borrowed_books'))
    else:
        flash(message, 'error')
        return redirect(request.referrer or url_for('main.book_detail', book_id=book_id))


@user_bp.route('/reservation/cancel/<reservation_id>', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    """Cancel a reservation."""
    res = Reservation.get_by_id(reservation_id)
    
    # Validation: Chỉ chủ sở hữu mới được hủy
    if not res or res.user_id != g.user.id:
        flash('Reservation not found or access denied', 'error')
        return redirect(url_for('user.reservations'))
    
    success, msg = res.cancel()
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'error')
        
    return redirect(url_for('user.reservations'))