from fastapi import APIRouter, Depends

from models.user import User
from schemas.user_schema import UserResponse
from security.basic_auth import current_user

router = APIRouter(prefix="/api", tags=["authentication"])


@router.get("/me", response_model=UserResponse)
def get_current_user(user: User = Depends(current_user)):
    return user
