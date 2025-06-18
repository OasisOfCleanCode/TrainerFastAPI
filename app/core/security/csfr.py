# app/core/security/csfr.py

from fastapi import Request, HTTPException, status


async def validate_csrf_token(request: Request):
    if 'http://127.0.0.1:5000/docs' or 'https://api.anwill.fun/docs' in request.headers.get('referer'):
        return
    user_agent = request.headers.get("User-Agent", "")
    if "Postman" in user_agent or "Insomnia" in user_agent or "Swagger" in user_agent:
        return  # Пропустить проверку CSRF
    # Извлекаем CSRF-токен из заголовка и cookie
    csrf_token_header = request.headers.get("X-CSRF-Token")
    csrf_token_cookie = request.cookies.get("csrf_token")

    # Проверяем, совпадают ли токены
    if not csrf_token_header or not csrf_token_cookie or csrf_token_header != csrf_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid"
        )
