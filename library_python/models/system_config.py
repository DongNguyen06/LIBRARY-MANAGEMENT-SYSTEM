import json
from typing import Any, Dict
from models.database import get_db
from config.config import Config


class SystemConfig:
    """System configuration settings manager.
    
    Manages dynamic configuration stored in the database.
    Falls back to Config.py constants if DB values are missing.
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        'max_borrowed_books': 5,
        'borrow_duration': 14,
        'reservation_hold_time': 2, # Days
        'late_fee_per_day': 10000.0,
        'renewal_limit': 1
    }

    @staticmethod
    def get() -> Dict[str, Any]:
        """Get current system configuration from DB."""
        db = get_db()
        result = db.execute('SELECT config_data FROM system_config WHERE id = 1').fetchone()
        
        if result:
            try:
                return json.loads(result['config_data'])
            except json.JSONDecodeError:
                return SystemConfig.DEFAULT_CONFIG.copy()
        return SystemConfig.DEFAULT_CONFIG.copy()

    @staticmethod
    def get_value(key: str, default: Any = None, type_cast: type = str) -> Any:
        """Helper: Get specific config value from DB, fallback to provided default."""
        current_config = SystemConfig.get()
        
        if key in current_config:
            val = current_config[key]
            try:
                if type_cast == bool and isinstance(val, str):
                    return val.lower() in ('true', '1', 'yes', 'on')
                return type_cast(val)
            except (ValueError, TypeError):
                return default
        
        return default

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        """Get integer config value."""
        return SystemConfig.get_value(key, default, int)

    @staticmethod
    def get_float(key: str, default: float = 0.0) -> float:
        """Get float config value."""
        return SystemConfig.get_value(key, default, float)

    @staticmethod
    def update(config_data: Dict[str, Any]) -> bool:
        """Update system configuration in DB."""
        db = get_db()
        
        current_config = SystemConfig.get()
        current_config.update(config_data)
        
        config_json = json.dumps(current_config)

        result = db.execute('SELECT id FROM system_config WHERE id = 1').fetchone()

        if result:
            db.execute('UPDATE system_config SET config_data = ? WHERE id = 1', (config_json,))
        else:
            db.execute('INSERT INTO system_config (id, config_data) VALUES (1, ?)', (config_json,))

        db.commit()
        return True