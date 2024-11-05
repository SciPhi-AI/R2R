from pydantic import BaseModel

from shared.abstractions import Token
from shared.api.models.base import ResultsWrapper


class TokenResponse(BaseModel):
    access_token: Token
    refresh_token: Token


class GenericMessageResponse(BaseModel):
    message: str


# Create wrapped versions of each response
WrappedTokenResponse = ResultsWrapper[TokenResponse]
WrappedGenericMessageResponse = ResultsWrapper[GenericMessageResponse]
