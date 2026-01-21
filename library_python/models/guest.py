class Guest:
    def __init__(self):
        self.id = None
        self.name = "Guest"
        self.email = None
        self.role = "guest"
        self.fines = 0.0
        self.favorites = []

    def is_staff(self):
        return False
        
    def is_admin(self):
        return False
    
    @property
    def is_authenticated(self):
        return False
    
    @property
    def is_active(self):
        return False
    
    @property
    def is_anonymous(self):
        return True
    
    def get_id(self):
        return None
        
    def can_borrow(self):
        return False
    
    def pay_fine(self, amount):
        return False
        
    def to_dict(self):
        return {
            'id': None,
            'name': 'Guest',
            'role': 'guest'
        }

    def __bool__(self):
        return False
    
    def __nonzero__(self):
        return False