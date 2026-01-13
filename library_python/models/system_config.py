"""System configuration model for managing system settings.

This module provides functionality for storing and retrieving
dynamic system configuration settings from the database.
"""
import json
from typing import Any, Dict

from models.database import get_db


class SystemConfig:
    """System configuration settings manager.

    This class provides static methods for getting and updating
    system configuration. No instances are created.

    Attributes:
        DEFAULT_CONFIG: Default configuration values used when
            no configuration exists in the database.
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        'max_borrowed_books': 3,
        'borrow_duration': 14,
        'reservation_hold_time': 3,
        'late_fee_per_day': 1.0,
        'renewal_limit': 2
    }

    @staticmethod
    def get() -> Dict[str, Any]:
        """Get current system configuration.

        Returns:
            Dictionary containing all configuration settings.
        """
        db = get_db()
        result = db.execute('SELECT config_data FROM system_config WHERE id = 1').fetchone()
        
        if result:
            return json.loads(result['config_data'])
        return SystemConfig.DEFAULT_CONFIG.copy()

    @staticmethod
    def update(config_data: Dict[str, Any]) -> bool:
        """Update system configuration.

        Args:
            config_data: Dictionary containing configuration settings.

        Returns:
            True if update was successful.
        """
        db = get_db()
        config_json = json.dumps(config_data)

        # Check if config exists
        result = db.execute('SELECT id FROM system_config WHERE id = 1').fetchone()

        if result:
            db.execute('UPDATE system_config SET config_data = ? WHERE id = 1', (config_json,))
        else:
            db.execute('INSERT INTO system_config (id, config_data) VALUES (1, ?)', (config_json,))

        db.commit()
        return True
