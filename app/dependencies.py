from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_db

DatabaseSession = Annotated[Session, Depends(get_db)]


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Administrative API key")


def require_api_key(x_api_key: Annotated[str | None, Depends(api_key_header)] = None) -> None:
    configured = get_settings().api_key
    if not configured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Calculation API is not configured")
    if x_api_key is None or not compare_digest(x_api_key, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


CalculationAccess = Annotated[None, Depends(require_api_key)]
