"""
Library Management System - Flask Application
Main application file
"""
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from functools import wraps
from datetime import datetime, timedelta
import os
from models.database import init_db, get_db
from models.user import User
from models.book import Book
from models.borrow import Borrow
from models.review import Review
from models.notification import Notification
from models.chat_message import ChatMessage
from config.config import Config
from scheduled_tasks import start_scheduler, shutdown_scheduler
import atexit

app = Flask(__name__)
app.config.from_object(Config)

# Initialize SocketIO for real-time chat
# Force threading mode to avoid eventlet errors
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database
with app.app_context():
    init_db()

# Start scheduled background tasks
start_scheduler(app)

# Ensure scheduler shuts down gracefully
atexit.register(shutdown_scheduler)

# Store online users (user_id -> socket_id)
online_users = {}


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page', 'warning')
                return redirect(url_for('login'))
            
            user = User.get_by_id(session['user_id'])
            if not user:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('home'))
            
            # Admin has all permissions (including staff permissions)
            if user.role == 'admin':
                return f(*args, **kwargs)
            
            # Check if user has required role
            if user.role not in roles:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.context_processor
def inject_user():
    """Inject current user into all templates"""
    user = None
    unread_count = 0
    notification_count = 0
    if 'user_id' in session:
        user = User.get_by_id(session['user_id'])
        # Get unread message count
        unread_count = ChatMessage.get_unread_count(session['user_id'])
        # Get unread notification count
        notification_count = Notification.get_unread_count(session['user_id'])
    return dict(current_user=user, unread_messages=unread_count, unread_notifications=notification_count)


# ============= Routes =============

@app.route('/')
def home():
    """Home page with featured books"""
    new_arrivals = Book.get_new_arrivals(limit=4)
    most_borrowed = Book.get_most_borrowed(limit=4)
    top_rated = Book.get_top_rated(limit=4)
    
    return render_template('pages/home.html',
                         new_arrivals=new_arrivals,
                         most_borrowed=most_borrowed,
                         top_rated=top_rated)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        user = User.login(email, password)
        if user:
            session['user_id'] = user.id
            session['user_role'] = user.role
            session.permanent = remember
            
            # Log login activity
            from models.system_log import SystemLog
            SystemLog.add(
                'User Login',
                f'{user.name} ({user.role}) logged in from email {email}',
                'info',
                user.id
            )
            
            flash(f'Welcome back, {user.name}!', 'success')
            
            # Redirect to intended page or dashboard
            next_page = request.args.get('next')
            
            # Create response to set cookie
            if user.role == 'admin':
                response = redirect(next_page or url_for('admin_dashboard'))
            elif user.role == 'staff':
                response = redirect(next_page or url_for('staff_dashboard'))
            else:
                response = redirect(next_page or url_for('user_dashboard'))
            
            # Save email to cookie if remember me is checked
            if remember:
                response.set_cookie('remembered_email', email, max_age=30*24*60*60)  # 30 days
            else:
                response.set_cookie('remembered_email', '', max_age=0)  # Clear cookie
            
            return response
        else:
            # Log failed login attempt
            from models.system_log import SystemLog
            SystemLog.add(
                'Failed Login Attempt',
                f'Failed login attempt for email: {email}',
                'warning',
                None
            )
            flash('Invalid email or password', 'error')
    
    # Get remembered email from cookie
    remembered_email = request.cookies.get('remembered_email', '')
    return render_template('pages/login.html', remembered_email=remembered_email)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register page"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        phone = request.form.get('phone')
        birthday = request.form.get('birthday')
        
        # Validate phone number: only digits, max 10 digits
        if phone:
            if not phone.isdigit():
                flash('Phone number can only contain digits, no special characters!', 'error')
                return render_template('pages/register.html')
            if len(phone) > 10:
                flash('Phone number cannot exceed 10 digits!', 'error')
                return render_template('pages/register.html')
        
        if User.create(email, password, name, phone, birthday):
            # Log registration
            from models.system_log import SystemLog
            SystemLog.add(
                'New User Registration',
                f'New user registered: {name} ({email})',
                'info',
                None
            )
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Registration failed. Email may already exist.', 'error')
    
    return render_template('pages/register.html')


@app.route('/logout')
def logout():
    """Logout user"""
    user_id = session.get('user_id')
    user_name = session.get('name', 'Unknown')
    
    if user_id:
        from models.system_log import SystemLog
        user = User.get_by_id(user_id)
        if user:
            SystemLog.add(
                'User Logout',
                f'{user.name} ({user.role}) logged out',
                'info',
                user_id
            )
    
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_name', None)
    session.pop('user_role', None)
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page"""
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate passwords match
        if new_password != confirm_password:
            flash('Confirmation password does not match!', 'error')
            return render_template('pages/forgot_password.html')
        
        # Check if user exists
        user = User.get_by_email(email)
        if not user:
            flash('Email does not exist in the system!', 'error')
            return render_template('pages/forgot_password.html')
        
        # Reset password using werkzeug (consistent with registration)
        from werkzeug.security import generate_password_hash
        hashed_password = generate_password_hash(new_password)
        
        db = get_db()
        db.execute('UPDATE users SET password = ? WHERE email = ?', 
                  (hashed_password, email))
        db.commit()
        
        # Log password reset
        from models.system_log import SystemLog
        SystemLog.add(
            'Password Reset',
            f'{user.name} reset their password',
            'warning',
            user.id
        )
        
        flash('Password reset successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('pages/forgot_password.html')


@app.route('/search')
def search():
    """Search books page"""
    query = request.args.get('q', '')
    search_by = request.args.get('searchBy', 'title')
    sort_by = request.args.get('sort', 'title')
    category = request.args.get('category', '')
    
    books = Book.search(query, search_by, sort_by, category)
    categories = Book.get_all_categories()
    
    return render_template('pages/search.html',
                         books=books,
                         categories=categories,
                         query=query,
                         search_by=search_by,
                         sort_by=sort_by,
                         selected_category=category)


@app.route('/book/<book_id>')
def book_detail(book_id):
    """Book detail page"""
    book = Book.get_by_id(book_id)
    if not book:
        flash('Book not found', 'error')
        return redirect(url_for('search'))
    
    # Get reviews with Review model
    reviews = Review.get_book_reviews_with_details(book_id)
    rating_stats = Review.get_book_rating_stats(book_id)
    
    is_favorite = False
    can_borrow = False
    can_reserve = False
    can_review = False
    user_review = None
    is_borrowed = False
    is_reserved = False
    
    if 'user_id' in session:
        user = User.get_by_id(session['user_id'])
        is_favorite = book_id in user.favorites
        
        if user.role == 'user':
            # Check if user already borrowed or reserved this book
            borrowed_books = Borrow.get_user_borrowed_books(user.id)
            reserved_books = Borrow.get_user_reserved_books(user.id)
            
            # Check for both 'borrowed' and 'pending_pickup' status
            # User shouldn't be able to borrow again if they have pending pickup
            is_borrowed = any(b.book_id == book_id and b.status in ['borrowed', 'pending_pickup'] 
                            for b in borrowed_books)
            # Reservation objects have different structure - check book_id only
            is_reserved = any(r.book_id == book_id and r.status == 'waiting' 
                            for r in reserved_books)
            
            # CORRECTED LOGIC (Senior Dev requirement):
            # - Show BORROW button ONLY when: available_copies > 0
            # - Show RESERVE button ONLY when: available_copies == 0
            if not is_borrowed and not is_reserved:
                if book.available_copies > 0:
                    can_borrow = True  # Book in stock → Show BORROW
                    can_reserve = False
                else:
                    can_borrow = False
                    can_reserve = True  # Book out of stock → Show RESERVE
            
            # DEBUG: Log button states for troubleshooting
            print(f"\n{'='*60}")
            print(f"[BOOK DETAIL DEBUG] Book: {book.title} (ID: {book.id})")
            print(f"  → Total Copies: {book.total_copies}")
            print(f"  → Available Copies: {book.available_copies}")
            print(f"  → User borrowed this book: {is_borrowed}")
            print(f"  → User reserved this book: {is_reserved}")
            print(f"  → SHOW BORROW button: {can_borrow}")
            print(f"  → SHOW RESERVE button: {can_reserve}")
            print(f"{'='*60}\n")
        
        can_review = Review.user_can_review(session['user_id'], book_id)
        
        # Check if user already has a review
        if not can_review:
            user_reviews = [r for r in reviews if r['user_id'] == session['user_id']]
            user_review = user_reviews[0] if user_reviews else None
    
    return render_template('pages/book_detail.html',
                         book=book,
                         reviews=reviews,
                         rating_stats=rating_stats,
                         is_favorite=is_favorite,
                         can_borrow=can_borrow,
                         can_reserve=can_reserve,
                         is_borrowed=is_borrowed,
                         is_reserved=is_reserved,
                         can_review=can_review,
                         user_review=user_review)


# ============= User Routes =============

@app.route('/dashboard')
@login_required
@role_required('user')
def user_dashboard():
    """User dashboard"""
    user = User.get_by_id(session['user_id'])
    borrowed_books = Borrow.get_user_borrowed_books(user.id)
    reserved_books = Borrow.get_user_reserved_books(user.id)
    overdue_books = Borrow.get_user_overdue_books(user.id)
    upcoming_due = Borrow.get_upcoming_due_books(user.id, days=3)
    
    return render_template('pages/user/dashboard.html',
                         borrowed_books=borrowed_books,
                         reserved_books=reserved_books,
                         overdue_books=overdue_books,
                         upcoming_due=upcoming_due)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    user = User.get_by_id(session['user_id'])
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        birthday = request.form.get('birthday')
        
        if user.update(name, phone, birthday):
            flash('Profile updated successfully', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Failed to update profile', 'error')
    
    return render_template('pages/user/profile.html', user=user)


@app.route('/borrowed-books')
@login_required
@role_required('user')
def borrowed_books():
    """View borrowed books"""
    user = User.get_by_id(session['user_id'])
    borrowed_books = Borrow.get_user_borrowed_books(user.id)
    
    return render_template('pages/user/borrowed_books.html',
                         borrowed_books=borrowed_books)


@app.route('/reservations')
@login_required
@role_required('user')
def user_reservations():
    """View user's book reservations"""
    from models.reservation import Reservation
    user = User.get_by_id(session['user_id'])
    reservations = Reservation.get_user_reservations(user.id)
    
    return render_template('pages/user/reservations.html',
                         reservations=reservations)


@app.route('/api/reserve/<book_id>', methods=['POST'])
@login_required
@role_required('user')
def reserve_book(book_id):
    """Create a reservation for a book"""
    from models.reservation import Reservation
    from models.book import Book
    
    user = User.get_by_id(session['user_id'])
    book = Book.get_by_id(book_id)
    
    if not book:
        return jsonify({'success': False, 'message': 'Book not found'}), 404
    
    # Check if user already has an active reservation for this book
    existing = Reservation.get_user_book_reservation(user.id, book_id)
    if existing and existing.status in ['waiting', 'ready']:
        return jsonify({'success': False, 'message': 'You already have an active reservation for this book'}), 400
    
    # Create reservation - HANDLE TUPLE RETURN (reservation, message)
    reservation, message = Reservation.create(user.id, book_id)
    
    if reservation:
        return jsonify({
            'success': True, 
            'message': message or 'Book reserved successfully! You will be notified when it becomes available.',
            'reservation_id': reservation.id
        })
    else:
        return jsonify({'success': False, 'message': message or 'Failed to create reservation'}), 400


@app.route('/api/cancel-reservation/<reservation_id>', methods=['POST'])
@login_required
@role_required('user')
def cancel_reservation(reservation_id):
    """Cancel a book reservation"""
    from models.reservation import Reservation
    
    user = User.get_by_id(session['user_id'])
    reservation = Reservation.get_by_id(reservation_id)
    
    if not reservation:
        return jsonify({'success': False, 'message': 'Reservation not found'}), 404
    
    if reservation.user_id != user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    success, message = reservation.cancel()
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@app.route('/favorites')
@login_required
@role_required('user')
def favorites():
    """View favorite books"""
    user = User.get_by_id(session['user_id'])
    favorite_books = user.get_favorite_books()
    
    return render_template('pages/user/favorites.html',
                         favorite_books=favorite_books)


@app.route('/notifications')
@login_required
@role_required('user')
def notifications():
    """View notifications"""
    # To be implemented
    return render_template('pages/user/notifications.html')


@app.route('/chat')
@login_required
@role_required('user', 'staff')
def chat():
    """Chat page"""
    # To be implemented
    return render_template('pages/chat.html')


# ============= Staff Routes =============

@app.route('/staff/dashboard')
@login_required
@role_required('staff')
def staff_dashboard():
    """Staff dashboard"""
    from models.book import Book
    from models.user import User
    from models.reservation import Reservation
    
    # Get statistics - UPDATED: Get pending_pickup instead of waiting
    pending_borrows = Borrow.get_user_borrows_by_status('pending_pickup')
    borrowed_books = Borrow.get_user_borrows_by_status('borrowed')  # Get all currently borrowed books
    overdue_books = Borrow.get_overdue_borrows()
    all_books = Book.get_all()
    
    # Get all reservations for tracking
    all_reservations = Reservation.get_all()
    
    # Calculate stats
    stats = {
        'borrowed': Borrow.get_active_borrows_count(),
        'overdue': len(overdue_books),
        'fines': sum(borrow.get_fine_amount() for borrow in overdue_books),
        'members': User.get_total_users(),
        'unread_messages': 0  # TODO: implement chat
    }
    
    # Get popular books
    popular_books = sorted(all_books, key=lambda x: x.borrow_count, reverse=True)[:10]
    
    return render_template('pages/staff/dashboard.html',
                         pending_borrows=pending_borrows,
                         borrowed_books=borrowed_books,
                         overdue_books=overdue_books,
                         all_books=all_books,
                         all_reservations=all_reservations,
                         popular_books=popular_books,
                         stats=stats)


@app.route('/staff/send-notifications')
@login_required
@role_required('staff')
def staff_send_notifications():
    """Staff send notifications page"""
    return render_template('pages/staff/send_notifications.html')


@app.route('/staff/approve/<borrow_id>', methods=['POST'])
@login_required
@role_required('staff')
def staff_approve_borrow(borrow_id):
    """Approve borrow request (pickup confirmation)"""
    # Get borrow record
    borrow = Borrow.get_by_id(borrow_id)
    if not borrow:
        flash('Borrow request not found', 'error')
        return redirect(url_for('staff_dashboard'))
    
    # Use approve_pickup for pending_pickup status
    if borrow.status == 'pending_pickup':
        success, message = borrow.approve_pickup()
        if success:
            flash(f'Pickup approved! Book is now borrowed. {message}', 'success')
        else:
            flash(f'Failed to approve: {message}', 'error')
    else:
        flash('Only pending pickup requests can be approved', 'error')
    
    return redirect(url_for('staff_dashboard'))


@app.route('/staff/reject/<borrow_id>', methods=['POST'])
@login_required
@role_required('staff')
def staff_reject_borrow(borrow_id):
    """Reject borrow request"""
    borrow = Borrow.get_by_id(borrow_id)
    if borrow and borrow.status == 'pending_pickup':
        success, message = borrow.cancel()
        if success:
            flash(f'Request rejected and book returned to inventory', 'success')
        else:
            flash(f'Failed to reject: {message}', 'error')
    else:
        flash('Only pending pickup requests can be rejected', 'error')
    return redirect(url_for('staff_dashboard'))


@app.route('/staff/process-borrow', methods=['POST'])
@login_required
@role_required('staff')
def staff_process_borrow():
    """Process direct book borrowing"""
    user_email = request.form.get('user_email')
    book_isbn = request.form.get('book_isbn')
    
    from models.user import User
    from models.book import Book
    
    user = User.get_by_email(user_email)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('staff_dashboard'))
    
    book = Book.get_by_isbn(book_isbn)
    if not book:
        flash('Book not found', 'error')
        return redirect(url_for('staff_dashboard'))
    
    if book.available_copies <= 0:
        flash('Book is not available', 'error')
        return redirect(url_for('staff_dashboard'))
    
    # Create and immediately approve borrow
    borrow, message = Borrow.create(user.id, book.id)
    if borrow and Borrow.approve_borrow_by_id(borrow.id)[0]:
        flash(f'Book "{book.title}" borrowed successfully to {user.name}', 'success')
    else:
        flash('Failed to process borrow', 'error')
    
    return redirect(url_for('staff_dashboard'))


@app.route('/staff/book/edit', methods=['POST'])
@login_required
@role_required('staff')
def staff_edit_book():
    """Edit book information (staff/admin)"""
    book_id = request.form.get('book_id')
    title = request.form.get('title')
    author = request.form.get('author')
    description = request.form.get('description')
    total_copies = int(request.form.get('total_copies', 1))
    available_copies = int(request.form.get('available_copies', 0))
    
    from models.book import Book
    book = Book.get_by_id(book_id)
    
    if not book:
        flash('Book not found', 'error')
        return redirect(url_for('staff_dashboard'))
    
    # Validate available copies doesn't exceed total
    if available_copies > total_copies:
        flash('Available copies cannot exceed total copies', 'error')
        return redirect(url_for('staff_dashboard'))
    
    # Update book
    db = get_db()
    db.execute('''
        UPDATE books 
        SET title = ?, author = ?, description = ?, 
            total_copies = ?, available_copies = ?
        WHERE id = ?
    ''', (title, author, description, total_copies, available_copies, book_id))
    db.commit()
    
    # Log the update
    from models.system_log import SystemLog
    user = User.get_by_id(session['user_id'])
    SystemLog.add(
        'Book Information Updated',
        f'{user.name} ({user.role}) updated book: "{title}"',
        'admin',
        user.id
    )
    
    flash('Book information updated successfully!', 'success')
    return redirect(url_for('staff_dashboard'))


@app.route('/staff/process-return', methods=['POST'])
@login_required
@role_required('staff')
def staff_process_return():
    """Process book return with condition assessment"""
    isbn = request.form.get('identifier')
    condition = request.form.get('condition', 'good')
    book_value = float(request.form.get('book_value', 0))
    fine_paid = request.form.get('fine_paid') == 'on'
    
    # Find book by ISBN
    from models.book import Book
    book = Book.get_by_isbn(isbn)
    
    if not book:
        flash('Book not found with this ISBN.', 'error')
        return redirect(url_for('staff_dashboard'))
    
    # Get the active borrow for this book
    db = get_db()
    cursor = db.execute('''
        SELECT id FROM borrows 
        WHERE book_id = ? AND status = 'borrowed'
        LIMIT 1
    ''', (book.id,))
    result = cursor.fetchone()
    
    if not result:
        flash('This book is not currently borrowed.', 'error')
        return redirect(url_for('staff_dashboard'))
    
    borrow = Borrow.get_by_id(result[0])
    
    if not borrow:
        flash('Borrow record not found.', 'error')
        return redirect(url_for('staff_dashboard'))
    
    # Process return directly using borrow object
    success, message = borrow.return_book(condition, book_value)
    
    if success:
        # Handle fine payment if needed
        if fine_paid:
            from models.user import User
            user = User.get_by_id(borrow.user_id)
            if user and user.fines > 0:
                user.pay_fine(user.fines)
        
        # Log the return
        from models.system_log import SystemLog
        from models.book import Book
        staff_user = User.get_by_id(session['user_id'])
        borrower = User.get_by_id(borrow.user_id)
        book = Book.get_by_id(borrow.book_id)
        
        if staff_user and borrower and book:
            SystemLog.add(
                'Book Return Processed',
                f'{staff_user.name} processed return: {borrower.name} returned "{book.title}"',
                'admin',
                session['user_id']
            )
        
        flash(f'Book returned successfully! {message}', 'success')
    else:
        flash(f'Failed to process return: {message}', 'error')
    
    return redirect(url_for('staff_dashboard'))


# ============= Admin Routes =============

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    """Admin dashboard"""
    from models.system_config import SystemConfig
    from models.system_log import SystemLog
    from models.borrow import Borrow
    
    # Get system statistics
    stats = {
        'total_books': Book.get_total_count(),
        'total_users': User.get_total_users(),
        'active_borrows': Borrow.get_active_borrows_count(),
        'overdue_count': Borrow.get_overdue_count(),
        'total_staff': User.get_users_by_role('staff'),
        'revenue': sum([u.fines for u in User.get_all_users()])
    }
    
    # Get system config
    config = SystemConfig.get()
    
    # Get recent logs (increase to 50 for better visibility)
    logs = SystemLog.get_recent(50)
    
    # Get borrowing trends (last 4 weeks)
    trends = []
    for week in range(1, 5):
        week_borrows = len([b for b in Borrow.get_all() if b.status in ['borrowed', 'returned']])
        trends.append({'week': f'Week {week}', 'count': week_borrows // (5-week+1)})
    
    return render_template('pages/admin/dashboard.html', 
                         stats=stats, 
                         config=config,
                         logs=logs,
                         trends=trends)


@app.route('/admin/send-notifications')
@login_required
@role_required('admin')
def admin_send_notifications():
    """Admin send notifications page"""
    return render_template('pages/admin/send_notifications.html')


@app.route('/admin/config/save', methods=['POST'])
@login_required
@role_required('admin')
def admin_save_config():
    """Save system configuration"""
    from models.system_config import SystemConfig
    from models.system_log import SystemLog
    
    config_data = {
        'max_borrowed_books': int(request.form.get('max_borrowed_books', 3)),
        'borrow_duration': int(request.form.get('borrow_duration', 14)),
        'reservation_hold_time': int(request.form.get('reservation_hold_time', 3)),
        'late_fee_per_day': float(request.form.get('late_fee_per_day', 1.0)),
        'renewal_limit': int(request.form.get('renewal_limit', 2))
    }
    
    # Get old config for comparison
    old_config = SystemConfig.get()
    
    SystemConfig.update(config_data)
    
    # Create detailed log of changes
    user = User.get_by_id(session['user_id'])
    changes = []
    if old_config.max_borrowed_books != config_data['max_borrowed_books']:
        changes.append(f"Max Borrowed Books: {old_config.max_borrowed_books} → {config_data['max_borrowed_books']}")
    if old_config.borrow_duration != config_data['borrow_duration']:
        changes.append(f"Borrow Duration: {old_config.borrow_duration} → {config_data['borrow_duration']} days")
    if old_config.late_fee_per_day != config_data['late_fee_per_day']:
        changes.append(f"Late Fee: ${old_config.late_fee_per_day} → ${config_data['late_fee_per_day']} per day")
    
    detail_msg = f"{user.name} updated: {', '.join(changes)}" if changes else f"{user.name} saved configuration (no changes)"
    SystemLog.add('Configuration Updated', detail_msg, 'admin', session['user_id'])
    
    flash('System configuration has been updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/logs/export')
@login_required
@role_required('admin')
def admin_export_logs():
    """Export system logs"""
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


@app.route('/admin/logs/clear', methods=['POST'])
@login_required
@role_required('admin')
def admin_clear_logs():
    """Clear old system logs"""
    from models.system_log import SystemLog
    
    days = int(request.form.get('days', 30))
    SystemLog.clear_old_logs(days)
    
    flash(f'Deleted logs older than {days} days!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============= API Routes =============
@app.route('/api/users', methods=['GET'])
@login_required
@role_required('admin', 'staff')
def api_get_users():
    """API endpoint to get users (admin/staff only)"""
    users = User.get_all_users()
    return jsonify({
        'success': True,
        'users': [{'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role} for u in users]
    })


@app.route('/api/books', methods=['GET'])
def api_get_books():
    """API endpoint to get books"""
    query = request.args.get('q', '')
    search_by = request.args.get('searchBy', 'title')
    
    books = Book.search(query, search_by)
    return jsonify({
        'success': True,
        'books': [book.to_dict() for book in books]
    })


@app.route('/api/books/<book_id>', methods=['GET'])
def api_get_book(book_id):
    """API endpoint to get book detail"""
    book = Book.get_by_id(book_id)
    if book:
        return jsonify({
            'success': True,
            'book': book.to_dict()
        })
    return jsonify({
        'success': False,
        'message': 'Book not found'
    }), 404


@app.route('/api/borrow/<book_id>', methods=['POST'])
@login_required
def api_borrow_book(book_id):
    """API endpoint to borrow a book"""
    user_id = session['user_id']
    success, message = Borrow.borrow_book(user_id, book_id)
    
    return jsonify({
        'success': success,
        'message': message
    })


@app.route('/api/cancel/<book_id>', methods=['POST'])
@login_required
def api_cancel_borrow(book_id):
    """API endpoint to cancel borrow/reservation"""
    user_id = session['user_id']
    success, message = Borrow.cancel_borrow_by_user(user_id, book_id)
    
    return jsonify({
        'success': success,
        'message': message
    })


@app.route('/api/return/<book_id>', methods=['POST'])
@login_required
def api_return_book(book_id):
    """API endpoint to return a book"""
    user_id = session['user_id']
    success, message = Borrow.return_book_by_user(user_id, book_id)
    
    return jsonify({
        'success': success,
        'message': message
    })


@app.route('/api/renew/<book_id>', methods=['POST'])
@login_required
def api_renew_book(book_id):
    """API endpoint to renew a book with custom days"""
    user_id = session['user_id']
    
    # Get days from request body (default to 7 if not provided)
    data = request.get_json() or {}
    days = data.get('days', 7)
    
    # Validate days
    try:
        days = int(days)
        if days < 1 or days > 7:
            return jsonify({
                'success': False,
                'message': 'Extension days must be between 1 and 7'
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            'success': False,
            'message': 'Invalid days value'
        }), 400
    
    # Call borrow service with custom days
    success, message = Borrow.renew_book_by_user(user_id, book_id, days)
    
    return jsonify({
        'success': success,
        'message': message
    })


@app.route('/api/favorites/<book_id>', methods=['POST', 'DELETE'])
@login_required
def api_manage_favorite(book_id):
    """API endpoint to add/remove favorite"""
    user_id = session['user_id']
    
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    
    if request.method == 'POST':
        if user.add_favorite(book_id):
            success, message = True, "Book added to favorites"
        else:
            success, message = False, "Book already in favorites"
    else:
        if user.remove_favorite(book_id):
            success, message = True, "Book removed from favorites"
        else:
            success, message = False, "Book not in favorites"
    
    return jsonify({
        'success': success,
        'message': message
    })


# ============= Review Routes =============

@app.route('/api/reviews/<book_id>', methods=['POST'])
@login_required
def submit_review(book_id):
    """Submit a review for a book"""
    user_id = session['user_id']
    rating = request.form.get('rating')
    comment = request.form.get('comment', '').strip()
    
    review, message = Review.submit_review(user_id, book_id, rating, comment)
    
    if review:
        flash('Your review has been submitted successfully!', 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('book_detail', book_id=book_id))


@app.route('/api/reviews/<review_id>/edit', methods=['POST'])
@login_required
def edit_review(review_id):
    """Edit an existing review"""
    user_id = session['user_id']
    rating = request.form.get('rating')
    comment = request.form.get('comment', '').strip()
    
    success, message = Review.update_review_by_user(review_id, user_id, rating, comment)
    
    if success:
        flash('Review has been updated!', 'success')
    else:
        flash(message, 'error')
    
    # Get book_id to redirect
    review = Review.get_by_id(review_id)
    book_id = review.book_id if review else None
    
    if book_id:
        return redirect(url_for('book_detail', book_id=book_id))
    return redirect(url_for('home'))


@app.route('/api/reviews/<review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    """Delete a review"""
    user_id = session['user_id']
    user_role = session.get('user_role', 'user')
    
    # Get book_id before deleting
    review = Review.get_by_id(review_id)
    book_id = review.book_id if review else None
    
    success, message = Review.delete_review_by_user(review_id, user_id, user_role)
    
    if success:
        flash('Review has been deleted!', 'success')
    else:
        flash(message, 'error')
    
    if book_id:
        return redirect(url_for('book_detail', book_id=book_id))
    return redirect(url_for('home'))


# ============= Error Handlers =============

@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return render_template('errors/404.html'), 404


# ============= Notification Routes =============

@app.route('/api/notifications')
@login_required
def get_notifications():
    """Get user notifications"""
    user_id = session['user_id']
    notifications = Notification.get_by_user(user_id)
    return jsonify({
        'success': True,
        'notifications': [n.to_dict() for n in notifications]
    })


@app.route('/api/notifications/<notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    Notification.mark_as_read(notification_id)
    return jsonify({'success': True, 'message': 'Marked as read'})


@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    user_id = session['user_id']
    Notification.mark_all_as_read(user_id)
    return jsonify({'success': True, 'message': 'All notifications marked as read'})


@app.route('/api/notifications/<notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """Delete a notification"""
    Notification.delete(notification_id)
    return jsonify({'success': True, 'message': 'Notification deleted'})


@app.route('/api/notifications/send', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def send_notification():
    """Send notification to users (admin/staff only)"""
    data = request.get_json()
    
    title = data.get('title')
    message = data.get('message')
    notification_type = data.get('type', 'info')
    target = data.get('target', 'all')  # 'all' or 'specific'
    user_ids = data.get('user_ids', [])
    
    user = User.get_by_id(session['user_id'])
    
    if target == 'all':
        notifications, msg = Notification.send_to_all_with_validation(
            notification_type, title, message, user.role
        )
    else:
        notifications, msg = Notification.send_to_specific_with_validation(
            user_ids, notification_type, title, message, user.role
        )
    
    if notifications:
        # Send real-time notification via SocketIO
        for notif in notifications:
            if notif.user_id in online_users:
                socketio.emit('new_notification', notif.to_dict(), 
                            room=online_users[notif.user_id])
        
        # Log notification sending
        from models.system_log import SystemLog
        SystemLog.add(
            'Notification Sent',
            f'{user.name} ({user.role}) sent notification: "{title}" to {len(notifications)} users',
            'admin',
            session['user_id']
        )
        
        return jsonify({'success': True, 'message': msg})
    else:
        return jsonify({'success': False, 'message': msg}), 400


# ============= Chat Routes =============

@app.route('/api/chat/conversations')
@login_required
def get_conversations():
    """Get recent conversations"""
    user_id = session['user_id']
    conversations = ChatMessage.get_recent_conversations_with_details(user_id)
    return jsonify({'success': True, 'conversations': conversations})


@app.route('/api/chat/messages/<partner_id>')
@login_required
def get_messages(partner_id):
    """Get messages with a specific user"""
    user_id = session['user_id']
    messages = ChatMessage.get_conversation(user_id, partner_id)
    
    # Mark as read
    ChatMessage.mark_as_read(user_id, partner_id)
    
    return jsonify({
        'success': True,
        'messages': [msg.to_dict() for msg in messages]
    })


@app.route('/api/chat/staff')
@login_required
def get_staff_list():
    """Get list of staff members for users to chat with"""
    staff = ChatMessage.get_available_staff()
    return jsonify({'success': True, 'staff': staff})


@app.route('/api/chat/unread')
@login_required
def get_unread_count():
    """Get unread message count"""
    user_id = session['user_id']
    count = ChatMessage.get_unread_count(user_id)
    return jsonify({'success': True, 'count': count})


# ============= SocketIO Events =============

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if 'user_id' in session:
        user_id = session['user_id']
        online_users[user_id] = request.sid
        emit('user_online', {'user_id': user_id}, broadcast=True)
        print(f"User {user_id} connected with socket {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if 'user_id' in session:
        user_id = session['user_id']
        if user_id in online_users:
            del online_users[user_id]
        emit('user_offline', {'user_id': user_id}, broadcast=True)
        print(f"User {user_id} disconnected")


@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a chat message"""
    if 'user_id' not in session:
        emit('error', {'message': 'Please login first'})
        print("❌ Unauthenticated send_message attempt")
        return
    
    sender_id = session['user_id']
    receiver_id = data.get('receiver_id')
    message = data.get('message')
    
    # Validate inputs
    if not receiver_id:
        emit('error', {'message': 'Receiver not specified'})
        print(f"❌ No receiver_id from sender {sender_id}")
        return
    
    if not message or not message.strip():
        emit('error', {'message': 'Message cannot be empty'})
        print(f"❌ Empty message from sender {sender_id}")
        return
    
    # Save message to database
    chat_message, error = ChatMessage.send_message(sender_id, receiver_id, message)
    
    if chat_message:
        message_data = chat_message.to_dict()
        
        # Get sender info
        sender = User.get_by_id(sender_id)
        if sender:
            message_data['sender_name'] = sender.name
        
        # Send confirmation to sender
        emit('message_sent', message_data)
        print(f"✅ Message from {sender_id} to {receiver_id}: '{message[:30]}...'")
        
        # Send to receiver if online
        if receiver_id in online_users:
            socketio.emit('new_message', message_data, room=online_users[receiver_id])
            print(f"  → Delivered to online receiver")
        else:
            print(f"  → Receiver offline, stored in DB")
    else:
        emit('error', {'message': error or 'Failed to send message'})
        print(f"❌ Send failed: {error}")


@socketio.on('typing')
def handle_typing(data):
    """Handle typing indicator"""
    if 'user_id' not in session:
        return
    
    sender_id = session['user_id']
    receiver_id = data.get('receiver_id')
    is_typing = data.get('is_typing', False)
    
    # Send typing indicator to receiver if online
    if receiver_id in online_users:
        socketio.emit('user_typing', {
            'user_id': sender_id,
            'is_typing': is_typing
        }, room=online_users[receiver_id])


@socketio.on('mark_read')
def handle_mark_read(data):
    """Mark messages as read"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    sender_id = data.get('sender_id')
    
    ChatMessage.mark_as_read(user_id, sender_id)
    emit('messages_marked_read', {'sender_id': sender_id})


# ============= Teardown =============

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection"""
    from models.database import close_db
    close_db(exception)


@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    return render_template('errors/500.html'), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
