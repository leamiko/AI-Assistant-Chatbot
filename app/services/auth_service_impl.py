from datetime import datetime

from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.common import utils
from app.core import google_auth, oauth2
from app.schemas.session import SessionCreate
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin, UserOut, UserUpdate
from app.services.auth_service import AuthService
from app.services.email_service_impl import EmailServiceImpl
from app.services.session_service_impl import SessionServiceImpl
from app.services.user_service_impl import UserServiceImpl


class AuthServiceImpl(AuthService):

    def __init__(self) -> None:
        self.__user_service = UserServiceImpl()
        self.__session_service = SessionServiceImpl()
        self.__email_service = EmailServiceImpl()

    def sign_up(self, db: Session, user: UserCreate) -> UserOut:
        """
        Create a new user.
        Parameters:
        user (UserCreate): The user data to create a new user.
        db (Session): The database session.
        Returns:
        UserOut: The created user data.
        """
        # Hash the password
        hashed_password = utils.hash(user.password)
        user.password = hashed_password
        # Create the user using the user service
        new_user = self.__user_service.create(db=db, user=user)
        return new_user

    def sign_in(self, db: Session, user_credentials: UserLogin) -> Token:

        user = self.__user_service.get_by_email_or_fail(
            db=db, email=user_credentials.email
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Invalid Credentials"
            )

        if not utils.verify(user_credentials.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Invalid Credentials"
            )
        access_token: str = oauth2.create_access_token(data={"user_id": str(user.id)})

        # Create a new session
        expires_at = utils.get_expires_at()
        new_session: SessionCreate = SessionCreate(
            token=access_token, user_id=user.id, expires_at=expires_at
        )

        token_data = self.__session_service.create(db=db, session=new_session)

        return Token(access_token=token_data.token, token_type="bearer")

    async def verify_user(self, db: Session, token: str) -> Token:
        current_user = oauth2.get_current_user(db=db, token=token)
        self.__user_service.update_is_verified(db=db, email=current_user.email)
        session = self.__session_service.update_expires_at(
            db=db, token=token, expires_at=utils.get_expires_at()
        )
        return Token(access_token=session.token, token_type="bearer")
    
    async def handle_google_callback(self, request: Request, db: Session):
        token = await google_auth.authorize_access_token(request)
        user_info = token.get("userinfo")
        if user_info:
            request.session["user"] = dict(user_info)
            user_found = self.__user_service.check_user_exists(db=db, email=user_info["email"])
            if user_found:
                user = self.__user_service.get_details_by_email(db=db, email=user_info["email"])
                is_verified = user.is_verified
                if is_verified:
                    token_data = self.__session_service.create_session(db=db, user_id=str(user.id), expires_at=utils.get_expires_at())
                    return Token(access_token=token_data.token, token_type="bearer")
                else:
                    token_data = self.__session_service.create_session(db=db, user_id=str(user.id), expires_at=datetime.now())
                    await self.__email_service.send_verification_email(user_info, token_data.token)
                    return RedirectResponse(url="https://raw.githubusercontent.com/DNAnh01/assets/main/02.1.%20Sign%20up%20-%20Success.png")

            else:
                user = UserUpdate(
                    email=user_info["email"],
                    display_name=user_info["name"],
                    password=user_info["at_hash"],
                    avatar_url=user_info["picture"],
                    is_verified=False,
                )
                new_user = self.create(db=db, user=user)
                token_data = self.__session_service.create_session(db=db, user_id=str(new_user.id), expires_at=datetime.now())
                await self.__email_service.send_verification_email(user_info, token_data.token)
                return RedirectResponse(url="https://raw.githubusercontent.com/DNAnh01/assets/main/02.1.%20Sign%20up%20-%20Success.png")