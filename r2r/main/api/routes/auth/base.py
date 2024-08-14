from typing import TYPE_CHECKING

from fastapi import Body, Depends, Path
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from r2r.base.api.models.auth.requests import (
    CreateUserRequest,
    DeleteUserRequest,
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshTokenRequest,
    UserPutRequest,
    VerifyEmailRequest,
)
from r2r.base.api.models.auth.responses import (
    GenericMessageResponse,
    WrappedGenericMessageResponse,
    WrappedTokenResponse,
    WrappedUserResponse,
)

from ..base_router import BaseRouter

if TYPE_CHECKING:
    from ....engine import R2REngine

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def login_form_to_request(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> LoginRequest:
    return LoginRequest(
        username=form_data.username, password=form_data.password
    )


class AuthRouter(BaseRouter):
    def __init__(self, engine: "R2REngine"):
        super().__init__(engine)
        if self.engine.providers.auth:
            self.setup_routes()

    def setup_routes(self):
        @self.router.post("/register", response_model=WrappedUserResponse)
        @self.base_endpoint
        async def register_app(user: CreateUserRequest):
            result = await self.engine.aregister(user)
            return result

        @self.router.post(
            "/verify_email", response_model=WrappedGenericMessageResponse
        )
        @self.base_endpoint
        async def verify_email_app(request: VerifyEmailRequest):
            result = await self.engine.averify_email(request.verification_code)
            return GenericMessageResponse(message=result["message"])

        @self.router.post("/login", response_model=WrappedTokenResponse)
        @self.base_endpoint
        async def login_app(
            request: LoginRequest = Depends(login_form_to_request),
        ):
            login_result = await self.engine.alogin(
                request.username, request.password
            )
            return login_result

        @self.router.get("/user", response_model=WrappedUserResponse)
        @self.base_endpoint
        async def get_user_app(
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            return auth_user

        @self.router.put("/user", response_model=WrappedUserResponse)
        @self.base_endpoint
        async def put_user_app(
            profile_update: UserPutRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            return await self.engine.aupdate_user(
                auth_user.id, profile_update.dict(exclude_unset=True)
            )

        @self.router.post(
            "/refresh_access_token", response_model=WrappedTokenResponse
        )
        @self.base_endpoint
        async def refresh_access_token_app(
            request: RefreshTokenRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            refresh_result = await self.engine.arefresh_access_token(
                user_email=auth_user.email,
                refresh_token=request.refresh_token,
            )
            return refresh_result

        @self.router.post(
            "/change_password", response_model=WrappedGenericMessageResponse
        )
        @self.base_endpoint
        async def change_password_app(
            password_change: PasswordChangeRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            result = await self.engine.achange_password(
                auth_user,
                password_change.current_password,
                password_change.new_password,
            )
            return WrappedGenericMessageResponse(message=result["message"])

        @self.router.post(
            "/request_password_reset",
            response_model=WrappedGenericMessageResponse,
        )
        @self.base_endpoint
        async def request_password_reset_app(
            reset_request: PasswordResetRequest,
        ):
            result = await self.engine.arequest_password_reset(
                reset_request.email
            )
            return WrappedGenericMessageResponse(message=result["message"])

        @self.router.post(
            "/reset_password/{reset_token}",
            response_model=WrappedGenericMessageResponse,
        )
        @self.base_endpoint
        async def reset_password_app(
            reset_token: str = Path(...),
            reset_confirm: PasswordResetConfirmRequest = Body(...),
        ):
            result = await self.engine.aconfirm_password_reset(
                reset_token, reset_confirm.new_password
            )
            return WrappedGenericMessageResponse(message=result["message"])

        @self.router.post(
            "/logout", response_model=WrappedGenericMessageResponse
        )
        @self.base_endpoint
        async def logout_app(
            request: LogoutRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            result = await self.engine.alogout(request.token)
            return WrappedGenericMessageResponse(message=result["message"])

        @self.router.delete(
            "/user", response_model=WrappedGenericMessageResponse
        )
        @self.base_endpoint
        async def delete_user_app(
            delete_request: DeleteUserRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if (
                auth_user.id != delete_request.user_id
                and not auth_user.is_superuser
            ):
                raise Exception("User ID does not match authenticated user")
            result = await self.engine.adelete_user(
                delete_request.user_id, delete_request.password
            )
            return GenericMessageResponse(message=result["message"])
