from datetime import datetime, timezone

from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dao.user import UserDAO
from app.db.sessions import TransactionSessionDep
from app.utils.logger import logger

from app.core.exceptions import (
    TokenNotFoundException,
    TokenExpiredException,
    UserNotFoundException,
    UpdateException,
)

from app.db.models.user import (
    EmailVerificationToken,
    ChangeEmailVerificationToken,
    ResetPasswordToken,
)

from app.db.schemas.user import (
    CheckTokenModel,
    CheckEmailModel,
    ResetPasswordSchema,
    SUserInfoRole,
)


background_router = APIRouter(prefix="/background_router", tags=["Background"])


@background_router.get("/email/verify/{token}", response_class=HTMLResponse)
async def verify_email(token: str = Path(), db: AsyncSession = TransactionSessionDep):
    """
    ## Endpoint верификации email адреса.

    ### Описание
    - Ручной способ верификации по токену.
    - Возвращает сообщение о статусе операции.
    - Endpoint доступен для всех.

    ### Требования
    - Этот эндпоинт требует передачи данных в строке запроса.
    - Пользователь не должен быть авторизован.
    """
    verify_token = CheckTokenModel(token=token)
    token_data = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token == verify_token.token
        )
    )
    token_data = token_data.scalar_one_or_none()
    if not token_data:
        return TokenNotFoundException
    if datetime.now(timezone.utc) > token_data.expires_at or token_data.ban:
        return TokenExpiredException
    email_schema = CheckEmailModel(email=token_data.email)
    check_user = await UserDAO.find_one_user_or_none(db=db, filters=email_schema)
    if not check_user:
        return UserNotFoundException
    token_data.ban = True
    check_user.is_email_confirmed = True
    await db.flush()
    return JSONResponse(
        status_code=200,
        content={"message": "Email Successfully confirmed"},
        headers={"X-Success-Code": "2032"},
    )


@background_router.get("/email/change/verify/{token}")
async def verify_email_for_change_email(
    token: str = Path(), db: AsyncSession = TransactionSessionDep
):
    """
    ## Endpoint верификации нового email адреса.

    ### Описание
    - Ручной способ верификации нового email адреса по токену.
    - Возвращает сообщение о статусе операции и меняет email при удаче.
    - Endpoint доступен для всех.

    ### Требования
    - Этот эндпоинт требует передачи данных в строке запроса.
    - Пользователь не должен быть авторизован.
    """
    verify_token = CheckTokenModel(token=token)
    token_data = await db.execute(
        select(ChangeEmailVerificationToken).where(
            ChangeEmailVerificationToken.token == verify_token.token
        )
    )
    token_data = token_data.scalar_one_or_none()
    if not token_data:
        return TokenNotFoundException
    if datetime.now(timezone.utc) > token_data.expires_at or token_data.ban:
        return TokenExpiredException
    email_schema = CheckEmailModel(email=token_data.email)
    check_user = await UserDAO.find_one_user_or_none(db=db, filters=email_schema)
    if not check_user:
        return UserNotFoundException
    try:

        token_data.ban = True

        check_user.email = token_data.new_email
        check_user.is_email_confirmed = True
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при обновлении email: {e}")
        raise UpdateException
    user = SUserInfoRole.model_validate(check_user)
    answer = user.model_dump(exclude_none=True)
    return JSONResponse(
        status_code=200, content=answer, headers={"X-Success-Code": "2032"}
    )


@background_router.post("/password/apply")
async def applying_new_password(
    form_data: ResetPasswordSchema = Depends(ResetPasswordSchema.as_form),
    db: AsyncSession = TransactionSessionDep,
) -> JSONResponse:
    """
    ## Endpoint сброса пароля.

    ### Описание
    - Ручной способ сброса пароля. На него с фронта приходят данные для обновления пароля после перехода по ссылке, которую пользователе получил по email.
    - Возвращает сообщение о статусе операции.
    - Endpoint доступен для всех.

    ### Требования
    - Этот эндпоинт требует передачи данных в теле запроса в виде **form_data (application/x-www-form-urlecoded**).
    - Пользователь не должен быть авторизован.
    """

    verify_token = CheckTokenModel(token=form_data.token)
    token_data = await db.execute(
        select(ResetPasswordToken).where(ResetPasswordToken.token == verify_token.token)
    )
    token_data = token_data.scalar_one_or_none()
    if not token_data:
        return TokenNotFoundException
    if datetime.now(timezone.utc) > token_data.expires_at or token_data.ban:
        return TokenExpiredException
    email_schema = CheckEmailModel(email=token_data.email)
    check_user = await UserDAO.find_one_user_or_none(db=db, filters=email_schema)
    if not check_user:
        return UserNotFoundException
    check_user.password = form_data.password
    await db.flush()
    return JSONResponse(
        status_code=200,
        content={"message": "The password is successfully updated"},
        headers={"X-Success-Code": "2033"},
    )
