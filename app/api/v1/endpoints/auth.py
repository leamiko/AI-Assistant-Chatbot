"""
    Sign up
    Sign in
    Sign in with Google
"""

from datetime import datetime

from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api import deps
from app.common import utils
from app.common.email_template import email_template
from app.core import google_auth, oauth2
from app.core.google_auth import oauth
from app.models.session import Session
from app.schemas.session import SessionCreate
from app.schemas.token import Token
from app.schemas.user import (UserCreate, UserInDB, UserLogin, UserOut,
                              UserUpdate)
from app.services.auth_service_impl import AuthServiceImpl
from app.services.email_service_impl import EmailServiceImpl
from app.services.session_service_impl import SessionServiceImpl
from app.services.user_service_impl import UserServiceImpl

router = APIRouter()

auth_service = AuthServiceImpl()
user_service = UserServiceImpl()
session_service = SessionServiceImpl()
email_service = EmailServiceImpl()

@router.post("/sign-up", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def sign_up(user: UserCreate, db: Session = Depends(deps.get_db)) -> UserOut:
    new_user = auth_service.sign_up(db=db, user=user)
    return new_user


@router.post("/sign-in", status_code=status.HTTP_200_OK, response_model=Token)
def sign_in(user: UserLogin, db: Session = Depends(deps.get_db)) -> Token:
    token = auth_service.sign_in(db=db, user_credentials=user)
    return token


@router.get("/sign-in-with-google")
async def sign_in_with_google(request: Request):
    redirect_uri = request.url_for("callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(deps.get_db)):
    return await auth_service.handle_google_callback(request, db)


@router.get("/verification")
async def verification(token: str, db: Session = Depends(deps.get_db)):
    return auth_service.verify_user(db=db, token=token)
