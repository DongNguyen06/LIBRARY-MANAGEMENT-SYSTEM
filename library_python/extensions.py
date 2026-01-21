from typing import Optional
from flask_socketio import SocketIO

# Initialize SocketIO without app binding
# Will be bound to app in create_app() function
socketio: SocketIO = SocketIO(
    cors_allowed_origins="*",
    async_mode='threading'
)