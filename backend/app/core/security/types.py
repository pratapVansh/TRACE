from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: str
    role: str


@dataclass(frozen=True, slots=True)
class RefreshTokenClaims:
    user_id: str
