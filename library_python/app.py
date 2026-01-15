"""Library Management System - Flask Application.

Refactored: Fat Models, Skinny Controllers pattern.
PEP 8 Compliant.
"""
import atexit
from functools import wraps

from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   session, url_for, g)
from flask_socketio import SocketIO, emit

from config.config import Config
from models import (
    init_db, User, Guest, Staff, Admin, 
    Book, Borrow, Review, ChatMessage, Notification
)
from scheduled_tasks import shutdown_scheduler, start_scheduler

app = Flask(__name__)
app.config.from_object(Config)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database
with app.app_context():
    init_db()

# Start background tasks
start_scheduler(app)
atexit.register(shutdown_scheduler)

online_users = {}

# --- User Loader & Context Processors ---

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = Guest()
    else:
        g.user = User.get_user_or_guest(user_id)

@app.context_processor
def inject_context():
    unread_count = 0
    notification_count = 0

    if g.user:
        unread_count = ChatMessage.get_unread_count(g.user.id)
        notification_count = Notification.get_unread_count(g.user.id)

    return dict(current_user=g.user,
                unread_messages=unread_count,
                unread_notifications=notification_count)

# --- Decorators ---

def login_required(f):
    """Decorator to require user login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """Decorator to require specific user roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))

            user = User.get_by_id(session['user_id'])
            if not user:
                session.clear()
                return redirect(url_for('login'))

            if user.is_admin():
                return f(*args, **kwargs)

            if user.role in roles:
                return f(*args, **kwargs)

            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('home'))
        return decorated_function
    return decorator

# --- Authentication Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'

        user = User.login(email, password)
        if user:
            session['user_id'] = user.id
            session['user_role'] = user.role
            session.permanent = remember
            flash(f'Welcome back, {user.name}!', 'success')

            next_page = request.args.get('next')
            if user.is_admin():
                return redirect(next_page or url_for('admin_dashboard'))
            elif user.is_staff():
                return redirect(next_page or url_for('staff_dashboard'))
            else:
                return redirect(next_page or url_for('user_dashboard'))
        else:
            flash('Invalid email or password', 'error')

    remembered_email = request.cookies.get('remembered_email', '')
    return render_template('pages/login.html', remembered_email=remembered_email)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User.create(
            request.form.get('email'),
            request.form.get('password'),
            request.form.get('name'),
            request.form.get('phone'),
            request.form.get('birthday')
        )
        if user:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Registration failed. Email may already exist.', 'error')
    return render_template('pages/register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        user = User.get_by_email(request.form.get('email'))
        if user:
            success, message = user.reset_password(request.form.get('new_password'))
            flash(message, 'success' if success else 'error')
        else:
            flash('Email not found', 'error')
        return redirect(url_for('login'))
    return render_template('pages/forgot_password.html')

# --- Public & User Routes ---

@app.route('/')
def home():
    return render_template('pages/home.html',
                         new_arrivals=Book.get_new_arrivals(limit=4),
                         most_borrowed=Book.get_most_borrowed(limit=4),
                         top_rated=Book.get_top_rated(limit=4))

@app.route('/search')
def search():
    query = request.args.get('q', '')
    search_by = request.args.get('searchBy', 'title')
    sort_by = request.args.get('sort', 'title')
    category = request.args.get('category', '')
    
    return render_template('pages/search.html',
                         books=Book.search(query, search_by, sort_by, category),
                         categories=Book.get_all_categories(),
                         query=query, search_by=search_by, sort_by=sort_by,
                         selected_category=category)

@app.route('/book/<book_id>')
def book_detail(book_id):
    book = Book.get_by_id(book_id)
    if not book:
        flash('Book not found', 'error')
        return redirect(url_for('search'))

    # ADAPTED: Manually fetch reviews and convert to dict (since 'get_book_reviews_with_details' removed)
    review_objs = Review.get_by_book(book_id)
    reviews = [r.to_dict() for r in review_objs]
    
    # ADAPTED: Manually calculate stats (since 'get_book_rating_stats' removed)
    if review_objs:
        avg = round(sum(r.rating for r in review_objs) / len(review_objs), 1)
        dist = {i: 0 for i in range(1, 6)}
        for r in review_objs:
            dist[r.rating] += 1
        rating_stats = {'average': avg, 'count': len(review_objs), 'distribution': dist}
    else:
        rating_stats = {'average': 0, 'count': 0, 'distribution': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}}

    interaction_status = {
        'is_favorite': False, 'can_borrow': False, 'can_reserve': False,
        'is_borrowed': False, 'is_reserved': False, 'can_review': False, 
        'user_review': None
    }

    if g.user:
        interaction_status = g.user.get_book_interaction_status(book_id, book)

    return render_template('pages/book_detail.html',
                         book=book,
                         reviews=reviews,
                         rating_stats=rating_stats,
                         **interaction_status)

@app.route('/dashboard')
@login_required
@role_required('user')
def user_dashboard():
    user = User.get_by_id(session['user_id'])
    return render_template('pages/user/dashboard.html',
                         borrowed_books=Borrow.get_user_borrowed_books(user.id),
                         reserved_books=Borrow.get_user_reserved_books(user.id),
                         overdue_books=Borrow.get_user_overdue_books(user.id),
                         upcoming_due=Borrow.get_upcoming_due_books(user.id, days=3))

@app.route('/user/pay-fine', methods=['POST'])
@login_required
@role_required('user')
def pay_fine():
    user = User.get_by_id(session['user_id'])
    success, message = user.pay_fine(user.fines)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('user_dashboard'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.get_by_id(session['user_id'])
    if request.method == 'POST':
        success, message = user.update(
            request.form.get('name'),
            request.form.get('phone'),
            request.form.get('birthday')
        )
        flash(message, 'success' if success else 'error')
    return render_template('pages/user/profile.html', user=user)

@app.route('/borrowed-books')
@login_required
@role_required('user')
def borrowed_books():
    user = User.get_by_id(session['user_id'])
    return render_template('pages/user/borrowed_books.html', 
                         borrowed_books=Borrow.get_user_borrowed_books(user.id))

@app.route('/reservations')
@login_required
@role_required('user')
def user_reservations():
    from models.reservation import Reservation
    user = User.get_by_id(session['user_id'])
    return render_template('pages/user/reservations.html', 
                         reservations=Reservation.get_user_reservations(user.id))

@app.route('/favorites')
@login_required
@role_required('user')
def favorites():
    user = User.get_by_id(session['user_id'])
    return render_template('pages/user/favorites.html', 
                         favorite_books=user.get_favorite_books())

@app.route('/notifications')
@login_required
@role_required('user')
def notifications():
    return render_template('pages/user/notifications.html')

@app.route('/chat')
@login_required
def chat():
    return render_template('pages/chat.html')

# --- Staff Routes ---

@app.route('/staff/dashboard')
@login_required
@role_required('staff')
def staff_dashboard():
    staff = Staff.get_by_id(session['user_id'])
    from models.reservation import Reservation
    
    return render_template('pages/staff/dashboard.html',
                         pending_borrows=Borrow.get_user_borrows_by_status('pending_pickup'),
                         borrowed_books=Borrow.get_user_borrows_by_status('borrowed'),
                         overdue_books=Borrow.get_overdue_borrows(),
                         all_books=Book.get_all(),
                         all_reservations=Reservation.get_all(),
                         popular_books=Book.get_most_borrowed(limit=10),
                         stats=staff.get_stats())

@app.route('/staff/approve/<borrow_id>', methods=['POST'])
@login_required
@role_required('staff')
def staff_approve_borrow(borrow_id):
    staff = Staff.get_by_id(session['user_id'])
    success, message = staff.approve_borrow_request(borrow_id)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/reject/<borrow_id>', methods=['POST'])
@login_required
@role_required('staff')
def staff_reject_borrow(borrow_id):
    staff = Staff.get_by_id(session['user_id'])
    success, message = staff.reject_borrow_request(borrow_id)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/process-borrow', methods=['POST'])
@login_required
@role_required('staff')
def staff_process_borrow():
    staff = Staff.get_by_id(session['user_id'])
    success, message = staff.process_direct_borrow(
        request.form.get('user_email'), 
        request.form.get('book_isbn')
    )
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/process-return', methods=['POST'])
@login_required
@role_required('staff')
def staff_process_return():
    staff = Staff.get_by_id(session['user_id'])
    success, message = staff.process_book_return(
        request.form.get('identifier'),
        request.form.get('condition', 'good'),
        float(request.form.get('book_value', 0)),
        request.form.get('fine_paid') == 'on'
    )
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/book/edit', methods=['POST'])
@login_required
@role_required('staff')
def staff_edit_book():
    staff = Staff.get_by_id(session['user_id'])
    success, message = staff.update_book_info(
        request.form.get('book_id'),
        request.form.get('title'),
        request.form.get('author'),
        request.form.get('description'),
        int(request.form.get('total_copies', 1)),
        int(request.form.get('available_copies', 0))
    )
    flash(message, 'success' if success else 'error')
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/send-notifications')
@login_required
@role_required('staff')
def staff_send_notifications():
    return render_template('pages/staff/send_notifications.html')

# --- Admin Routes ---

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    from models.system_config import SystemConfig
    from models.system_log import SystemLog
    
    admin = Admin.get_by_id(session['user_id'])
    
    return render_template('pages/admin/dashboard.html',
                         stats=admin.get_stats(),
                         config=SystemConfig.get(),
                         logs=SystemLog.get_recent(50),
                         trends=[])

@app.route('/admin/config/save', methods=['POST'])
@login_required
@role_required('admin')
def admin_save_config():
    admin = Admin.get_by_id(session['user_id'])
    config_data = {
        'max_borrowed_books': int(request.form.get('max_borrowed_books', 3)),
        'borrow_duration': int(request.form.get('borrow_duration', 14)),
        'reservation_hold_time': int(request.form.get('reservation_hold_time', 3)),
        'late_fee_per_day': float(request.form.get('late_fee_per_day', 1.0)),
        'renewal_limit': int(request.form.get('renewal_limit', 2))
    }
    success, message = admin.save_system_config(config_data)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logs/clear', methods=['POST'])
@login_required
@role_required('admin')
def admin_clear_logs():
    admin = Admin.get_by_id(session['user_id'])
    success, message = admin.clear_system_logs(int(request.form.get('days', 30)))
    flash(message, 'success' if success else 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/send-notifications')
@login_required
@role_required('admin')
def admin_send_notifications():
    return render_template('pages/admin/send_notifications.html')

@app.route('/admin/logs/export')
@login_required
@role_required('admin')
def admin_export_logs():
    from models.system_log import SystemLog
    import csv
    from io import StringIO
    from flask import make_response
    
    logs = SystemLog.get_recent(1000)
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Timestamp', 'Action', 'Details', 'Type', 'User ID'])
    for log in logs:
        writer.writerow([log['timestamp'], log['action'], log['details'], log['log_type'], log.get('user_id', '')])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=system_logs.csv"
    output.headers["Content-type"] = "text/csv"
    return output

# --- API Endpoints ---

@app.route('/api/users', methods=['GET'])
@login_required
@role_required('admin', 'staff')
def api_get_users():
    users = User.get_all_users()
    return jsonify({
        'success': True,
        'users': [{'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role} for u in users]
    })

@app.route('/api/books', methods=['GET'])
def api_get_books():
    books = Book.search(request.args.get('q', ''), request.args.get('searchBy', 'title'))
    return jsonify({'success': True, 'books': [book.to_dict() for book in books]})

@app.route('/api/borrow/<book_id>', methods=['POST'])
@login_required
def api_borrow_book(book_id):
    # ADAPTED: Use Borrow.create directly instead of wrapper
    borrow, message = Borrow.create(session['user_id'], book_id)
    return jsonify({'success': borrow is not None, 'message': message})

@app.route('/api/reserve/<book_id>', methods=['POST'])
@login_required
def reserve_book(book_id):
    from models.reservation import Reservation
    res, msg = Reservation.create(session['user_id'], book_id)
    return jsonify({'success': bool(res), 'message': msg})

@app.route('/api/cancel/<book_id>', methods=['POST'])
@login_required
def api_cancel_borrow(book_id):
    # ADAPTED: Logic moved from deleted service wrapper 'cancel_borrow_by_user'
    borrows = Borrow.get_user_borrows(session['user_id'], status='pending_pickup')
    target = next((b for b in borrows if b.book_id == book_id), None)
    if target:
        success, message = target.cancel()
    else:
        success, message = False, "No pending borrow request found for this book"
    return jsonify({'success': success, 'message': message})

@app.route('/api/cancel-reservation/<reservation_id>', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    from models.reservation import Reservation
    res = Reservation.get_by_id(reservation_id)
    if res and res.user_id == session['user_id']:
        success, message = res.cancel()
        return jsonify({'success': success, 'message': message})
    return jsonify({'success': False, 'message': 'Reservation not found or unauthorized'}), 400

@app.route('/api/renew/<book_id>', methods=['POST'])
@login_required
def api_renew_book(book_id):
    days = request.get_json().get('days', 7)
    # ADAPTED: Logic moved from deleted service wrapper 'renew_book_by_user'
    borrows = Borrow.get_active_borrows(session['user_id'])
    target = next((b for b in borrows if b.book_id == book_id and b.status == 'borrowed'), None)
    if target:
        success, message = target.renew(days)
    else:
        success, message = False, "No active borrow found for this book"
    return jsonify({'success': success, 'message': message})

@app.route('/api/favorites/<book_id>', methods=['POST', 'DELETE'])
@login_required
def api_manage_favorite(book_id):
    user = User.get_by_id(session['user_id'])
    if request.method == 'POST':
        success = user.add_favorite(book_id)
        msg = "Added to favorites" if success else "Already in favorites"
    else:
        success = user.remove_favorite(book_id)
        msg = "Removed from favorites" if success else "Not in favorites"
    return jsonify({'success': success, 'message': msg})

# --- Notification APIs ---

@app.route('/api/notifications', methods=['GET'])
@login_required
def api_get_notifications():
    """Get all notifications for current user."""
    notifs = Notification.get_by_user(session['user_id'])
    return jsonify({'success': True, 'notifications': [n.to_dict() for n in notifs]})

@app.route('/api/notifications/send', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def api_send_notification():
    """Send a notification (Admin/Staff only)."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    title = data.get('title')
    message = data.get('message')
    type_ = data.get('type', 'info')
    target = data.get('target', 'all')
    user_ids = data.get('user_ids', [])
    
    # ADAPTED: Removed validation wrapper calls, using core logic directly
    if not title or not message:
        return jsonify({'success': False, 'message': 'Title and message are required'})

    try:
        if target == 'all':
            notifications = Notification.send_to_all_users(type_, title, message)
            return jsonify({'success': True, 'message': f'Sent to {len(notifications)} users'})
        
        elif target == 'specific' and user_ids:
            notifications = Notification.send_to_specific_users(user_ids, type_, title, message)
            return jsonify({'success': True, 'message': f'Sent to {len(notifications)} users'})
            
        return jsonify({'success': False, 'message': 'Invalid target or empty user list'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/notifications/<notif_id>/read', methods=['POST'])
@login_required
def api_read_notification(notif_id):
    """Mark a specific notification as read."""
    Notification.mark_as_read(notif_id)
    return jsonify({'success': True})

@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def api_read_all_notifications():
    """Mark all notifications as read."""
    Notification.mark_all_as_read(session['user_id'])
    return jsonify({'success': True})

@app.route('/api/notifications/<notif_id>', methods=['DELETE'])
@login_required
def api_delete_notification(notif_id):
    """Delete a notification."""
    Notification.delete(notif_id)
    return jsonify({'success': True})

# --- Chat API ---

@app.route('/api/chat/staff', methods=['GET'])
@login_required
def api_chat_staff():
    try:
        staff_list = ChatMessage.get_available_staff()
        return jsonify({'success': True, 'staff': staff_list})
    except Exception as error:
        return jsonify({'success': False, 'message': str(error), 'staff': []}), 500

@app.route('/api/chat/conversations', methods=['GET'])
@login_required
def api_chat_conversations():
    user_id = session['user_id']
    try:
        conversations = ChatMessage.get_recent_conversations_with_details(user_id)
        return jsonify({'success': True, 'conversations': conversations})
    except Exception as error:
        return jsonify({'success': False, 'message': str(error), 'conversations': []}), 500

@app.route('/api/chat/messages/<partner_id>', methods=['GET'])
@login_required
def api_chat_messages(partner_id):
    user_id = session['user_id']
    try:
        messages = ChatMessage.get_conversation(user_id, partner_id)
        ChatMessage.mark_as_read(user_id, partner_id)
        return jsonify({
            'success': True,
            'messages': [msg.to_dict() for msg in messages],
        })
    except Exception as error:
        return jsonify({'success': False, 'message': str(error), 'messages': []}), 500

@app.route('/api/chat/unread', methods=['GET'])
@login_required
def api_chat_unread():
    user_id = session['user_id']
    try:
        count = ChatMessage.get_unread_count(user_id)
        return jsonify({'success': True, 'count': count})
    except Exception as error:
        return jsonify({'success': False, 'message': str(error), 'count': 0}), 500

# --- Review Routes ---

@app.route('/api/reviews/<book_id>', methods=['POST'])
@login_required
def submit_review(book_id):
    # ADAPTED: Call Review.create directly instead of wrapper
    review, message = Review.create(
        session['user_id'],
        book_id,
        request.form.get('rating'),
        request.form.get('comment')
    )
    if review:
        flash('Review submitted', 'success')
    else:
        flash(message, 'error')
    return redirect(url_for('book_detail', book_id=book_id))

@app.route('/api/reviews/<review_id>/edit', methods=['POST'])
@login_required
def edit_review(review_id):
    rating = request.form.get('rating')
    comment = request.form.get('comment', '')
    
    # ADAPTED: Logic moved from deleted service wrapper 'update_review_by_user'
    review = Review.get_by_id(review_id)
    if not review:
        success, message = False, "Review not found"
    elif review.user_id != session['user_id']:
        success, message = False, "You can only edit your own reviews"
    else:
        success, message = review.update(rating, comment)
        
    flash(message, 'success' if success else 'error')
    
    review_obj = Review.get_by_id(review_id)
    book_id = review_obj.book_id if review_obj else request.args.get('book_id')
    return redirect(url_for('book_detail', book_id=book_id))

@app.route('/reviews/<review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    user = User.get_by_id(session['user_id'])
    
    # ADAPTED: Logic moved from deleted service wrapper 'delete_review_by_user'
    review = Review.get_by_id(review_id)
    if not review:
        success, message = False, "Review not found"
    elif review.user_id != user.id and not user.is_admin():
        success, message = False, "Unauthorized"
    else:
        success, message = Review.delete(review_id)

    flash(message, 'success' if success else 'error')

    book_id = request.args.get('book_id')
    if book_id:
        return redirect(url_for('book_detail', book_id=book_id))
    return redirect(url_for('home'))

# --- SocketIO Events ---

@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        online_users[session['user_id']] = request.sid

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session and session['user_id'] in online_users:
        del online_users[session['user_id']]

@socketio.on('send_message')
def handle_send_message(data):
    if 'user_id' not in session:
        return

    sender_id = session['user_id']
    receiver_id = data.get('receiver_id')
    message_text = data.get('message', '')

    chat_message, _ = ChatMessage.send_message(sender_id, receiver_id, message_text)
    if not chat_message:
        return

    payload = chat_message.to_dict()

    emit('new_message', payload, room=request.sid)

    receiver_sid = online_users.get(receiver_id)
    if receiver_sid:
        emit('new_message', payload, room=receiver_sid)

@socketio.on('typing')
def handle_typing(data):
    if 'user_id' not in session:
        return

    receiver_id = data.get('receiver_id')
    is_typing = data.get('is_typing', False)
    receiver_sid = online_users.get(receiver_id)
    if receiver_sid:
        emit('typing', {
            'sender_id': session['user_id'],
            'is_typing': is_typing,
        }, room=receiver_sid)

# --- Error Handlers ---

@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)