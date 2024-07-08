from ...engine import R2REngine
from .base_router import BaseRouter
from r2r.base import User, UserCreate, Token, TokenData

# Add these methods to your existing AuthRouter class
class AuthRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def setup_routes(self):
        @self.router.post("/register")
        def register(user: UserCreate):
            return self.engine.auth_provider.register_user(user)

        @self.router.post("/verify_email/{verification_code}")
        def verify_email(verification_code: str):
            return self.engine.auth_provider.verify_email(verification_code)

        @self.router.post("/login")
        def login(email: str, password: str):
            return self.engine.auth_provider.login(email, password)