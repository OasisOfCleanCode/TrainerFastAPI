"""
Этот модуль содержит функции для отправки писем пользователям:
- подтверждение email при регистрации,
- подтверждение нового email при смене,
- восстановление пароля.

Каждая функция:
1. Генерирует уникальный токен, который сохраняется в БД.
2. Формирует ссылку с токеном, ведущую на фронт (или другой сервис).
3. Подставляет ссылку в HTML-шаблон письма.
4. Отправляет письмо пользователю через почтовый сервис.

Шаблоны писем находятся в: templates/service_templates/emails/
Отправка производится через FastAPI-Mail (см. WorkingWithEmail).
"""

from urllib.parse import urljoin

from fastapi import HTTPException
from pydantic import EmailStr
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_urls_to_services
from app.core.templates import templates
from app.db.models import (
    EmailVerificationToken,
    ChangeEmailVerificationToken,
    ResetPasswordToken,
)
from app.db.sessions import TransactionSessionDep
from app.services.mail_sender.notifier import WorkingWithEmail
from app.utils.logger import logger


# === 1. Подтверждение email при регистрации ===
async def send_verify_email_to_user(email: EmailStr, db=TransactionSessionDep):
    """
    Отправляет письмо пользователю для подтверждения его email при регистрации.

    - Создаётся EmailVerificationToken и сохраняется в БД
    - Генерируется ссылка /email/verify/{token}
    - Подставляется в HTML-шаблон verify_email_address.html
    - Отправляется письмо с кнопкой "Подтвердить email"
    """
    token = EmailVerificationToken(email=email)
    try:
        db.add(token)
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка генерации токена для верификации email: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generate verify token to email"
        )

    base_url = get_urls_to_services().BASE_USER_URL
    verification_link = urljoin(base_url, f"email/verify/{token.token}")
    html_body = templates.env.get_template(
        "service_templates/emails/verify_email_address.html"
    ).render(link=verification_link)

    try:
        email_agent = WorkingWithEmail()
        subject = "Oasis of Clear COde. Подтверждение email адреса"

        await email_agent.send_email(subject=subject, body=html_body, emails=[email])

        return JSONResponse(
            status_code=200, content={"message": "Verification email sent"}
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения на email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending email")


# === 2. Подтверждение смены email ===
async def send_verify_change_email_to_user(
    email: EmailStr, new_email: EmailStr, db=TransactionSessionDep
):
    """
    Отправляет письмо на старый email, чтобы подтвердить смену адреса.

    - Создаётся ChangeEmailVerificationToken с текущим и новым email
    - Генерируется ссылка /email/change/verify/{token}
    - Подставляется в шаблон verify_change_email_address.html
    - Отправляется письмо со ссылкой подтверждения
    """
    token = ChangeEmailVerificationToken(email=email, new_email=new_email)
    try:
        db.add(token)
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка генерации токена для верификации email: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generate verify token to email"
        )

    base_url = get_urls_to_services().BASE_USER_URL
    verification_link = urljoin(base_url, f"/email/change/verify/{token.token}")
    html_body = templates.env.get_template(
        "service_templates/emails/verify_change_email_address.html"
    ).render(link=verification_link)

    try:
        email_agent = WorkingWithEmail()
        subject = "Oasis of Clear COde. Подтверждение email адреса"

        await email_agent.send_email(subject=subject, body=html_body, emails=[email])

        return JSONResponse(
            status_code=200,
            content={"message": "Verification email sent for change email"},
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения на email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending email")


# === 3. Сброс пароля ===
async def send_reset_password_to_user(email: EmailStr, db=TransactionSessionDep):
    """
    Отправляет письмо с ссылкой на восстановление пароля.

    - Генерирует ResetPasswordToken
    - Формирует ссылку /password/reset/{token}
    - Подставляет её в шаблон reset_password.html
    - Отправляет письмо пользователю
    """
    token = ResetPasswordToken(email=email)
    try:
        db.add(token)
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка генерации токена для сброса пароля: {e}")
        raise HTTPException(
            status_code=500, detail=f"Token generation error for password reset"
        )

    base_url = get_urls_to_services().BASE_USER_URL
    verification_link = urljoin(base_url, f"/password/reset/{token.token}")
    html_body = templates.env.get_template(
        "service_templates/emails/reset_password.html"
    ).render(link=verification_link)

    try:
        email_agent = WorkingWithEmail()
        subject = "Oasis of Clear COde. Подтверждение email адреса"

        await email_agent.send_email(subject=subject, body=html_body, emails=[email])

        return JSONResponse(status_code=200, content={"message": "Reset password sent"})
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения на email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending reset password")
