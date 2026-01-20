"""Flask extensions initialization module.

This module initializes all Flask extensions to prevent circular imports.
Extensions are initialized here and imported into app.py and other modules.
"""
from typing import Optional

from flask_socketio import SocketIO

# Initialize SocketIO without app binding
# Will be bound to app in create_app() function
socketio: SocketIO = SocketIO(
    cors_allowed_origins="*",
    async_mode='threading'
)

# You can add other extensions here as needed
# For example:
# db = SQLAlchemy()
# migrate = Migrate()
# login_manager = LoginManager()