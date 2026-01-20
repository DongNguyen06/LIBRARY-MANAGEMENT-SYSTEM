"""API endpoints for AJAX requests.

This module handles all JSON API endpoints for frontend interactions
including book operations, notifications, chat, and reviews.
"""
from typing import Dict, List, Tuple

from flask import Blueprint, jsonify, request, session

from models.book import Book
from models.borrow import Borrow
from models.chat_message import ChatMessage
from models.notification import Notification
from models.reservation import Reservation
from models.review import Review
from models.user import User
from utils.decorators import login_required, role_required

# Create API blueprint
api_bp = Blueprint('api', __name__)


# ==================== Book Operations ====================

@api_bp.route('/books', methods=['GET'])
def get_books():
    """Search books via API.
    
    Query params:
        q: Search query.
        searchBy: Field to search (title, author, category).
    
    Returns:
        JSON response with book list.
    """
    query = request.args.get('q', '')
    search_by = request.args.get('searchBy', 'title')
    
    books = Book.search(query, search_by)
    
    return jsonify({
        'success': True,
        'books': [book.to_dict() for book in books]
    })


@api_bp.route('/borrow/<book_id>', methods=['POST'])
@login_required
def borrow_book(book_id: str):
    """Create a borrow request for a book.
    
    ✅ FIXED: Now sends notification to user confirming the borrow request
    
    Args:
        book_id: Book identifier.
    
    Returns:
        JSON response with success status and message.
    """
    from models.notification import Notification
    
    borrow, message = Borrow.create(session['user_id'], book_id)
    
    # ✅ FIXED: Send notification when borrow request is successful
    if borrow:
        user = User.get_by_id(session['user_id'])
        book = Book.get_by_id(book_id)
        
        if user and book:
            # Calculate pickup deadline
            from datetime import datetime, timedelta
            pickup_deadline = (datetime.now() + timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
            
            Notification.create(
                user_id=session['user_id'],
                notification_type='success',
                title='Book Hold Confirmed',
                message=f'Your hold on "{book.title}" has been confirmed. '
                        f'Please pick it up within 48 hours ({pickup_deadline}). '
                        f'The due date will be 14 days from pickup.'
            )
    
    return jsonify({
        'success': borrow is not None,
        'message': message
    })


@api_bp.route('/reserve/<book_id>', methods=['POST'])
@login_required
def reserve_book(book_id: str):
    """Create a reservation for an unavailable book.
    
    Args:
        book_id: Book identifier.
    
    Returns:
        JSON response with success status and message.
    """
    reservation, message = Reservation.create(session['user_id'], book_id)
    return jsonify({
        'success': bool(reservation),
        'message': message
    })


@api_bp.route('/cancel/<book_id>', methods=['POST'])
@login_required
def cancel_borrow(book_id: str):
    """Cancel a pending borrow request.
    
    Args:
        book_id: Book identifier.
    
    Returns:
        JSON response with success status and message.
    """
    # Find pending borrow for this book
    borrows = Borrow.get_user_borrows(session['user_id'], status='pending_pickup')
    target_borrow = next((b for b in borrows if b.book_id == book_id), None)
    
    if target_borrow:
        success, message = target_borrow.cancel()
    else:
        success, message = False, "No pending borrow request found for this book"
    
    return jsonify({
        'success': success,
        'message': message
    })


@api_bp.route('/cancel-reservation/<reservation_id>', methods=['POST'])
@login_required
def cancel_reservation(reservation_id: str):
    """Cancel a book reservation.
    
    Args:
        reservation_id: Reservation identifier.
    
    Returns:
        JSON response with success status and message.
    """
    reservation = Reservation.get_by_id(reservation_id)
    
    if reservation and reservation.user_id == session['user_id']:
        success, message = reservation.cancel()
        return jsonify({
            'success': success,
            'message': message
        })
    
    return jsonify({
        'success': False,
        'message': 'Reservation not found or unauthorized'
    }), 400


@api_bp.route('/renew/<book_id>', methods=['POST'])
@login_required
def renew_book(book_id: str):
    """Renew a borrowed book.
    
    Args:
        book_id: Book identifier.
    
    Returns:
        JSON response with success status and message.
    """
    data = request.get_json() or {}
    days = data.get('days', 7)
    
    # Find active borrow for this book
    borrows = Borrow.get_active_borrows(session['user_id'])
    target_borrow = next(
        (b for b in borrows if b.book_id == book_id and b.status == 'borrowed'),
        None
    )
    
    if target_borrow:
        success, message = target_borrow.renew(days)
    else:
        success, message = False, "No active borrow found for this book"
    
    return jsonify({
        'success': success,
        'message': message
    })


@api_bp.route('/favorites/<book_id>', methods=['POST', 'DELETE'])
@login_required
def manage_favorite(book_id: str):
    """Add or remove a book from favorites.
    
    Args:
        book_id: Book identifier.
    
    Returns:
        JSON response with success status and message.
    """
    user = User.get_by_id(session['user_id'])
    
    if request.method == 'POST':
        success = user.add_favorite(book_id)
        message = "Added to favorites" if success else "Already in favorites"
    else:  # DELETE
        success = user.remove_favorite(book_id)
        message = "Removed from favorites" if success else "Not in favorites"
    
    return jsonify({
        'success': success,
        'message': message
    })


# ==================== User Management ====================

@api_bp.route('/users', methods=['GET'])
@login_required
@role_required('admin', 'staff')
def get_users():
    """Get list of all users (admin/staff only).
    
    Returns:
        JSON response with user list.
    """
    users = User.get_all_users()
    return jsonify({
        'success': True,
        'users': [
            {
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'role': u.role
            }
            for u in users
        ]
    })


# ==================== Notifications ====================

@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Get all notifications for current user.
    
    Returns:
        JSON response with notification list.
    """
    notifications = Notification.get_by_user(session['user_id'])
    return jsonify({
        'success': True,
        'notifications': [n.to_dict() for n in notifications]
    })


@api_bp.route('/notifications/send', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def send_notification():
    """Send notification to users (admin/staff only).
    
    JSON payload:
        title: Notification title.
        message: Notification message.
        type: Notification type (info, warning, success, urgent).
        target: 'all' or 'specific'.
        user_ids: List of user IDs (if target is 'specific').
    
    Returns:
        JSON response with success status and message.
    """
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'No data provided'
        }), 400
    
    title = data.get('title')
    message = data.get('message')
    notif_type = data.get('type', 'info')
    target = data.get('target', 'all')
    user_ids = data.get('user_ids', [])
    
    # Validation
    if not title or not message:
        return jsonify({
            'success': False,
            'message': 'Title and message are required'
        })
    
    try:
        if target == 'all':
            notifications = Notification.send_to_all_users(notif_type, title, message)
            return jsonify({
                'success': True,
                'message': f'Sent to {len(notifications)} users'
            })
        
        elif target == 'specific' and user_ids:
            notifications = Notification.send_to_specific_users(
                user_ids, notif_type, title, message
            )
            return jsonify({
                'success': True,
                'message': f'Sent to {len(notifications)} users'
            })
        
        return jsonify({
            'success': False,
            'message': 'Invalid target or empty user list'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_bp.route('/notifications/<notif_id>/read', methods=['POST'])
@login_required
def read_notification(notif_id: str):
    """Mark a notification as read.
    
    Args:
        notif_id: Notification identifier.
    
    Returns:
        JSON response with success status.
    """
    Notification.mark_as_read(notif_id)
    return jsonify({'success': True})


@api_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def read_all_notifications():
    """Mark all notifications as read for current user.
    
    Returns:
        JSON response with success status.
    """
    Notification.mark_all_as_read(session['user_id'])
    return jsonify({'success': True})


@api_bp.route('/notifications/<notif_id>', methods=['DELETE'])
@login_required
def delete_notification(notif_id: str):
    """Delete a notification.
    
    Args:
        notif_id: Notification identifier.
    
    Returns:
        JSON response with success status.
    """
    Notification.delete(notif_id)
    return jsonify({'success': True})


# ==================== Chat ====================

@api_bp.route('/chat/staff', methods=['GET'])
@login_required
def get_staff():
    """Get list of available staff members for chat.
    
    Returns:
        JSON response with staff list.
    """
    try:
        staff_list = ChatMessage.get_available_staff()
        return jsonify({
            'success': True,
            'staff': staff_list
        })
    except Exception as error:
        return jsonify({
            'success': False,
            'message': str(error),
            'staff': []
        }), 500


@api_bp.route('/chat/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get recent conversations for current user.
    
    Returns:
        JSON response with conversation list.
    """
    try:
        conversations = ChatMessage.get_recent_conversations_with_details(
            session['user_id']
        )
        return jsonify({
            'success': True,
            'conversations': conversations
        })
    except Exception as error:
        return jsonify({
            'success': False,
            'message': str(error),
            'conversations': []
        }), 500


@api_bp.route('/chat/messages/<partner_id>', methods=['GET'])
@login_required
def get_messages(partner_id: str):
    """Get conversation messages with a specific user.
    
    Args:
        partner_id: ID of the conversation partner.
    
    Returns:
        JSON response with message list.
    """
    try:
        messages = ChatMessage.get_conversation(session['user_id'], partner_id)
        ChatMessage.mark_as_read(session['user_id'], partner_id)
        
        return jsonify({
            'success': True,
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as error:
        return jsonify({
            'success': False,
            'message': str(error),
            'messages': []
        }), 500


@api_bp.route('/chat/unread', methods=['GET'])
@login_required
def get_unread_count():
    """Get count of unread chat messages.
    
    Returns:
        JSON response with unread count.
    """
    try:
        count = ChatMessage.get_unread_count(session['user_id'])
        return jsonify({
            'success': True,
            'count': count
        })
    except Exception as error:
        return jsonify({
            'success': False,
            'message': str(error),
            'count': 0
        }), 500


# ==================== Reviews ====================

@api_bp.route('/reviews/<book_id>', methods=['POST'])
@login_required
@role_required('user')  # STRICT: Only regular users can review
def submit_review(book_id: str):
    """Submit a review for a book.
    
    Restricted to regular users only. Admin and Staff cannot submit reviews.
    
    Args:
        book_id: Book identifier.
    
    Form data:
        rating: Rating value (1-5).
        comment: Review comment text.
    
    Returns:
        Redirect to book detail page.
    """
    from flask import flash, redirect, url_for
    # Verify user role (double-check)
    user = User.get_by_id(session['user_id'])
    if not user or user.role != 'user':
        flash('Only library members can submit reviews', 'error')
        return redirect(url_for('main.book_detail', book_id=book_id))
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    review, message = Review.create(
        session['user_id'],
        book_id,
        rating,
        comment
    )
    if review:
        flash('Review submitted', 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('main.book_detail', book_id=book_id))


@api_bp.route('/reviews/<review_id>/edit', methods=['POST'])
@login_required
@role_required('user')  # STRICT: Only regular users
def edit_review(review_id: str):
    """Edit an existing review.
    
    Restricted to regular users only. Users can only edit their own reviews.
    
    Args:
        review_id: Review identifier.
    
    Form data:
        rating: Updated rating value.
        comment: Updated review comment.
    
    Returns:
        Redirect to book detail page.
    """
    from flask import flash, redirect, url_for
    user = User.get_by_id(session['user_id'])
    if not user or user.role != 'user':
        flash('Only library members can edit reviews', 'error')
        return redirect(url_for('main.home'))
    rating = request.form.get('rating')
    comment = request.form.get('comment', '')
    review = Review.get_by_id(review_id)
    if not review:
        success, message = False, "Review not found"
    elif review.user_id != session['user_id']:
        success, message = False, "You can only edit your own reviews"
    else:
        success, message = review.update(rating, comment)
    flash(message, 'success' if success else 'error')
    # Get book_id for redirect
    review_obj = Review.get_by_id(review_id)
    book_id = review_obj.book_id if review_obj else request.args.get('book_id')
    return redirect(url_for('main.book_detail', book_id=book_id))


@api_bp.route('/reviews/<review_id>/delete', methods=['POST'])
@login_required
@role_required('user')  # STRICT: Only regular users
def delete_review(review_id: str):
    """Delete a review.
    
    Restricted to regular users only. Users can only delete their own reviews.
    Admin and Staff cannot delete reviews.
    
    Args:
        review_id: Review identifier.
    
    Returns:
        Redirect to book detail page or home.
    """
    from flask import flash, redirect, url_for
    user = User.get_by_id(session['user_id'])
    # Double-check user role
    if not user or user.role != 'user':
        flash('Only library members can delete reviews', 'error')
        return redirect(url_for('main.home'))
    review = Review.get_by_id(review_id)
    if not review:
        success, message = False, "Review not found"
    elif review.user_id != user.id:
        # REMOVED: and not user.is_admin()
        # Now ONLY the author can delete
        success, message = False, "You can only delete your own reviews"
    else:
        success, message = Review.delete(review_id)
    flash(message, 'success' if success else 'error')
    book_id = request.args.get('book_id')
    if book_id:
        return redirect(url_for('main.book_detail', book_id=book_id))
    return redirect(url_for('main.home'))