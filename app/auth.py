"""API key authentication via FastAPI dependency injection."""

import secrets
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Validate the API key from the X-API-Key header.

    Args:
        api_key: The API key value from the header, or None if missing.

    Returns:
        The validated API key string.

    Raises:
        HTTPException 401: If the header is missing.
        HTTPException 403: If the API key is invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include header: X-API-Key: <your-key>",
        )

    # compare_digest prevents timing attacks on the key comparison
    if not secrets.compare_digest(api_key, settings.agent_api_key):
        raise HTTPException(status_code=403, detail="Invalid API key.")

    return api_key
