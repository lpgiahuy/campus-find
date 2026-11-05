"""Auth Controller."""
from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user, get_service
from app.db.models import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenData, UserRead
from app.modules.auth.service import AuthService
from app.shared.schemas import ApiResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=ApiResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký tài khoản USER",
)
async def register(
    data: RegisterRequest,
    service: AuthService = Depends(get_service(AuthService)),
):
    user = await service.register(data)
    return ApiResponse(message="Đăng ký thành công", data=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=ApiResponse[TokenData],
    summary="Đăng nhập và nhận access token",
)
async def login(
    data: LoginRequest,
    service: AuthService = Depends(get_service(AuthService)),
):
    return ApiResponse(message="Đăng nhập thành công", data=await service.login(data))


@router.get(
    "/me",
    response_model=ApiResponse[UserRead],
    summary="Xem thông tin tài khoản đang đăng nhập",
)
async def me(user: User = Depends(get_current_user)):
    return ApiResponse(data=UserRead.model_validate(user))
