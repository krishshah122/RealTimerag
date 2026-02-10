import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from supabase import Client, create_client


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    # We intentionally don't crash the app here to allow running without Supabase
    supabase: Optional[Client] = None
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


security = HTTPBearer(auto_error=False)


class UserContext(BaseModel):
    id: str
    email: Optional[str] = None
    role: Optional[str] = None
    team: Optional[str] = None


async def _resolve_user_from_token(token: str) -> UserContext:
    """
    Decode the Supabase JWT and hydrate the user profile from the `profiles` table.

    Assumptions about the Supabase schema (see SQL you ran earlier):
    - Table: profiles
      - id (uuid, PK, matches auth.users.id / JWT `sub`)
      - email (text)
      - role (text)
      - team_name (text)  -- used as our team identifier
    """
    if not SUPABASE_JWT_SECRET:
        # Warning only, as we might use JWKS
        pass

    try:
        # 1. Get the header to check algorithm
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")

        if alg == "HS256":
            # Verify using shared secret
            claims = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        elif alg == "ES256" or alg == "RS256":
            # Verify using JWKS (Public Key)
            import httpx
            # Correct path for Supabase Auth v1 JWKS
            jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
            
            # TODO: Add caching for JWKS!
            with httpx.Client() as client:
                jwks = client.get(jwks_url).json()
            
            claims = jwt.decode(
                token,
                jwks, # python-jose can handle the JWKS dict directly
                algorithms=[alg],
                options={"verify_aud": False},
            )
        else:
             raise JWTError(f"Unsupported algorithm: {alg}")

    except Exception as e:
        # print(f"DEBUG: JWT Decode Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
        )

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    if supabase is None:
        # Allow running without Supabase backing store, but we still have an id from JWT.
        return UserContext(id=user_id)

    # Look up the profile to fetch role and team
    resp = supabase.table("profiles").select("*").eq("id", user_id).single().execute()

    if getattr(resp, "error", None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No profile found for user",
        )

    profile = resp.data or {}

    return UserContext(
        id=user_id,
        email=profile.get("email"),
        role=profile.get("role"),
        team=profile.get("team_name"),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None,
) -> UserContext:
    """
    FastAPI dependency to enforce authenticated access on sensitive routes.
    """
    # Prefer the user attached by middleware if present
    if getattr(request.state, "user", None) is not None:
        return request.state.user  # type: ignore[return-value]

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication",
        )

    user = await _resolve_user_from_token(credentials.credentials)
    if request is not None:
        request.state.user = user
    return user


async def auth_middleware(request: Request, call_next):
    """
    Middleware that eagerly decodes Supabase JWTs and attaches `request.state.user`.

    Routes can still enforce auth strictly by using the `get_current_user` dependency.
    """
    auth_header = request.headers.get("Authorization")
    user: Optional[UserContext] = None

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            user = await _resolve_user_from_token(token)
        except HTTPException:
            # We don't block the request here; route dependencies will enforce auth as needed.
            user = None

    request.state.user = user
    response = await call_next(request)
    return response

