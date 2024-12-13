from pydantic import BaseModel

from shared.abstractions import Token
from shared.api.models.base import R2RResults


class TokenResponse(BaseModel):
    access_token: Token
    refresh_token: Token


# Create wrapped versions of each response
WrappedTokenResponse = R2RResults[TokenResponse]
