from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8)


class TokenResponse(BaseModel):
	user_id: str
	access_token: str
	refresh_token: str
	expires_in: int
	token_type: str = "Bearer"


class RefreshRequest(BaseModel):
	refresh_token: str
