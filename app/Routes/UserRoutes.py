"""
User routes — operations on the user record.

Currently:
  GET /auth/me   return the authenticated user

Path stays under /auth/* to match the frontend's existing contract,
but the handler lives here because it's a user-domain read, not an
auth verification.
"""
from fastapi import APIRouter, Depends

from app.Dtos.UserDto.UserResponse import UserResponse
from app.Entities.User import User
from app.Services.UserService import UserService
from app.Dependencies import get_current_user, get_user_service

router = APIRouter(prefix="/auth", tags=["user"])


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
) -> UserResponse:
    return await users.get_me(str(current_user.id))