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


async def send_verify_email_to_user(email: EmailStr, db=TransactionSessionDep):
    token = EmailVerificationToken(email=email)
    try:
        db.add(token)
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка генерации токена для верификации email: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generate verify token to email"
        )

    verification_path = f"email/verify/{token.token}"
    base_url = get_urls_to_services().BASE_USER_URL
    verification_link = urljoin(base_url, verification_path)
    html_body = templates.env.get_template(
        "service_templates/emails/verify_email_address.html"
    ).render(link=verification_link)
    try:
        email_agent = WorkingWithEmail()
        subject = f"Oasis of Clear COde. Подтверждение email адреса"

        await email_agent.send_email(
            subject=subject,
            body=html_body,
            emails=[email],
        )

        return JSONResponse(
            status_code=200, content={"message": "Verification email sent"}
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения на email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending email")


async def send_verify_change_email_to_user(
    email: EmailStr, new_email: EmailStr, db=TransactionSessionDep
):
    token = ChangeEmailVerificationToken(email=email, new_email=new_email)
    try:
        db.add(token)
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка генерации токена для верификации email: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generate verify token to email"
        )

    verification_path = f"/email/change/verify/{token.token}"
    base_url = get_urls_to_services().BASE_USER_URL
    verification_link = urljoin(base_url, verification_path)
    html_body = templates.env.get_template(
        "service_templates/emails/verify_change_email_address.html"
    ).render(link=verification_link)

    try:
        email_agent = WorkingWithEmail()
        subject = f"Oasis of Clear COde. Подтверждение email адреса"

        await email_agent.send_email(
            subject=subject,
            body=html_body,
            emails=[email],
        )

        return JSONResponse(
            status_code=200,
            content={"message": "Verification email sent for change email"},
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения на email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending email")


async def send_reset_password_to_user(email: EmailStr, db=TransactionSessionDep):
    token = ResetPasswordToken(email=email)
    try:
        db.add(token)
        await db.flush()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка генерации токена для сброса пароля: {e}")
        raise HTTPException(
            status_code=500, detail=f"Token generation error for password reset"
        )
    # Формируем ссылку для верификации
    verification_path = f"/password/reset/{token.token}"
    base_url = get_urls_to_services().BASE_USER_URL
    verification_link = urljoin(base_url, verification_path)
    html_body = templates.env.get_template(
        "service_templates/emails/verify_change_email_address.html"
    ).render(link=verification_link)

    try:
        email_agent = WorkingWithEmail()
        subject = f"Oasis of Clear COde. Подтверждение email адреса"

        await email_agent.send_email(
            subject=subject,
            body=html_body,
            emails=[email],
        )

        return JSONResponse(status_code=200, content={"message": "Reset password sent"})
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения на email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error sending reset password")
