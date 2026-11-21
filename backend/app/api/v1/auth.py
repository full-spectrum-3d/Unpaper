"""POST /auth/token - logowanie kontem technicznym, wydanie JWT (spec §6.1, §10.1)."""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
async def issue_token() -> dict[str, object]:
    raise NotImplementedError
