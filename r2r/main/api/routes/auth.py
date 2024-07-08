from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from r2r.base import Token, TokenData, User, UserCreate

from ...engine import R2REngine
from .base_router import BaseRouter
from pydantic import BaseModel

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class UserResponse(BaseModel):
    results: User


class AuthRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def setup_routes(self):
        @self.router.post("/register", response_model=UserResponse)
        @self.base_endpoint
        async def register(user: UserCreate):
            return await self.engine.aregister_user(user)
        
        @self.router.post("/verify_email/{verification_code}")
        @self.base_endpoint
        async def verify_email(verification_code: str):
            return await self.engine.averify_email(verification_code)

        @self.router.post("/login", response_model=Token)
        @self.base_endpoint
        async def login(form_data: OAuth2PasswordRequestForm = Depends()):
            return await self.engine.alogin(form_data.username, form_data.password)

        @self.router.get("/users/me", response_model=User)
        @self.base_endpoint
        async def read_users_me(token: str = Depends(oauth2_scheme)):
            return await self.engine.aget_current_user(token)

        @self.router.post("/token/refresh", response_model=Token)
        @self.base_endpoint
        async def refresh_token(token: str = Depends(oauth2_scheme)):
            return await self.engine.arefresh_token(token)