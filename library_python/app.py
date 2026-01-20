"""Library Management System - Flask Application.

Refactored with Clean Architecture:
- Blueprints for route organization
- Extensions module to prevent circular imports
- PEP 8 compliance with type hints
- English comments and docstrings
"""
import atexit

from flask import Flask, g, session

from config.config import Config
from extensions import socketio
from models import Guest, Notification, User, init_db
from models.chat_message import ChatMessage
from routes import admin_bp, api_bp, auth_bp, main_bp, staff_bp, user_bp
from scheduled_tasks import shutdown_scheduler, start_scheduler


def create_app() -> Flask:
    """Create and configure the Flask application.
    
    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    socketio.init_app(app)
    
    # Initialize database
    with app.app_context():
        init_db()
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register context processors and hooks
    register_hooks(app)
    
    # Start background tasks
    start_scheduler(app)
    atexit.register(shutdown_scheduler)
    
    return app


def register_hooks(app: Flask) -> None:
    """Register application hooks and context processors.
    
    Args:
        app: Flask application instance.
    """
    @app.before_request
    def load_logged_in_user() -> None:
        """Load current user from session before each request."""
        user_id = session.get('user_id')
        if user_id is None:
            g.user = Guest()
        else:
            g.user = User.get_user_or_guest(user_id)

    @app.context_processor
    def inject_context() -> dict:
        """Inject global context variables into all templates.
        
        Returns:
            Dictionary of context variables.
        """
        unread_count = 0
        notification_count = 0

        if g.user and hasattr(g.user, 'id') and g.user.id:
            unread_count = ChatMessage.get_unread_count(g.user.id)
            notification_count = Notification.get_unread_count(g.user.id)

        return {
            'current_user': g.user,
            'unread_messages': unread_count,
            'unread_notifications': notification_count
        }

    @app.errorhandler(404)
    def not_found(error) -> tuple:
        """Handle 404 errors.
        
        Args:
            error: The error object.
            
        Returns:
            Rendered error page and 404 status code.
        """
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error) -> tuple:
        """Handle 500 errors.
        
        Args:
            error: The error object.
            
        Returns:
            Rendered error page and 500 status code.
        """
        from flask import render_template
        return render_template('errors/500.html'), 500


# Create app instance
app = create_app()

# Online users tracking for chat feature
online_users = {}


# SocketIO event handlers
@socketio.on('connect')
def handle_connect() -> None:
    """Handle client connection to SocketIO."""
    from flask import request
    if 'user_id' in session:
        online_users[session['user_id']] = request.sid


@socketio.on('disconnect')
def handle_disconnect() -> None:
    """Handle client disconnection from SocketIO."""
    if 'user_id' in session and session['user_id'] in online_users:
        del online_users[session['user_id']]


@socketio.on('send_message')
def handle_send_message(data: dict) -> None:
    """Handle incoming chat messages.
    
    Args:
        data: Dictionary containing message data (receiver_id, message).
    """
    from flask import request
    from flask_socketio import emit
    
    if 'user_id' not in session:
        return

    sender_id = session['user_id']
    receiver_id = data.get('receiver_id')
    message_text = data.get('message', '')

    chat_message, _ = ChatMessage.send_message(sender_id, receiver_id, message_text)
    if not chat_message:
        return

    payload = chat_message.to_dict()

    # Send to sender
    emit('new_message', payload, room=request.sid)

    # Send to receiver if online
    receiver_sid = online_users.get(receiver_id)
    if receiver_sid:
        emit('new_message', payload, room=receiver_sid)


@socketio.on('typing')
def handle_typing(data: dict) -> None:
    """Handle typing indicators.
    
    Args:
        data: Dictionary containing typing status (receiver_id, is_typing).
    """
    from flask_socketio import emit
    
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


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)