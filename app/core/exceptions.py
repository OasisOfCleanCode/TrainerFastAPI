from fastapi import HTTPException, status
from typing import Optional


class BaseAPIException(HTTPException):
    """Базовый класс для всех кастомных исключений"""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
        headers: Optional[dict] = None,
    ):
        headers = headers or {}
        headers["X-Error-Code"] = error_code
        super().__init__(status_code=status_code, detail=detail, headers=headers)


# --------------------------------------------------
# Аутентификация и авторизация (1xxx)
# --------------------------------------------------
class InvalidCredentialsException(BaseAPIException):
    """Ошибки входа"""

    def __init__(self, detail: str = "Неверные учетные данные"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, error_code="1003"
        )


class EmailOrPasswordInvalidException(InvalidCredentialsException):
    def __init__(self):
        super().__init__("Неверная почта или пароль")


class PhoneOrPasswordInvalidException(InvalidCredentialsException):
    def __init__(self):
        super().__init__("Неверный телефон или пароль")


class IncorrectPhoneOrEmailException(HTTPException):
    def __init__(self):
        super().__init__("Неверный формат ввода. Введите email или номер телефона.")


class RefreshPasswordInvalidException(InvalidCredentialsException):
    def __init__(self):
        super().__init__("Неверный пароль")


class CredentialsValidationException(BaseAPIException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось проверить учетные данные",
            error_code="1005",
        )


# --------------------------------------------------
# Токены (10xx)
# --------------------------------------------------
class TokenException(BaseAPIException):
    """Базовый класс для ошибок токенов"""

    def __init__(self, detail: str, error_code: str = "1011"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN, detail=detail, error_code=error_code
        )


class TokenExpiredException(TokenException):
    def __init__(self):
        super().__init__("Токен истек")


class TokenNotFoundException(TokenException):
    def __init__(self):
        super().__init__("Токен не найден")


class TokenGenerationException(TokenException):
    def __init__(self):
        super().__init__("Ошибка генерации токена")


class InvalidJWTException(TokenException):
    def __init__(self):
        super().__init__("Невалидный JWT токен")


class TokenMismatchException(TokenException):
    def __init__(self):
        super().__init__("Токены не совпадают")


class CSRFException(TokenException):
    def __init__(self):
        super().__init__("CSRF токен отсутствует или недействителен", error_code="1012")


class ForbiddenAccessException(HTTPException):
    def __init__(self):
        super().__init__("Недостаточно прав!")


# --------------------------------------------------
# Пользователи (11xx)
# --------------------------------------------------
class UserException(BaseAPIException):
    """Базовый класс для пользовательских ошибок"""

    def __init__(self, status_code: int, detail: str, error_code: str):
        super().__init__(status_code, detail, error_code)


class UserAlreadyExistsException(UserException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь уже зарегистрирован",
            error_code="1101",
        )


class UserNotFoundException(UserException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
            error_code="1102",
        )


class UserIdNotFoundException(UserException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Не найден ID пользователя",
            error_code="1103",
        )


class UserBannedException(UserException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь заблокирован",
            error_code="1104",
        )


# --------------------------------------------------
# Контакты (12xx)
# --------------------------------------------------
class ContactException(BaseAPIException):
    """Ошибки связанные с email/телефонами"""

    def __init__(self, status_code: int, detail: str, error_code: str):
        super().__init__(status_code, detail, error_code)


class EmailAlreadyExistsException(ContactException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email уже зарегистрирован",
            error_code="1201",
        )


class PhoneAlreadyExistsException(ContactException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Номер телефона уже зарегистрирован",
            error_code="1202",
        )


class InvalidContactFormatException(ContactException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат контакта (email или телефон)",
            error_code="1203",
        )


class ContactAvailableException(ContactException):
    """Успешная проверка доступности контакта"""

    def __init__(self, contact_type: str = "email"):
        super().__init__(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Нет зарегистрированного {contact_type}",
            error_code="1210",
        )


# --------------------------------------------------
# Роли (13xx)
# --------------------------------------------------
class RoleException(BaseAPIException):
    def __init__(self, status_code: int, detail: str, error_code: str):
        super().__init__(status_code, detail, error_code)


class RoleNotFoundException(RoleException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Роль не найдена",
            error_code="1301",
        )


class RoleAlreadyAssignedException(RoleException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Роль уже назначена пользователю",
            error_code="1302",
        )


class RoleNotAssignedException(RoleException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Роль не назначена пользователю",
            error_code="1303",
        )


# --------------------------------------------------
# Валидация (14xx)
# --------------------------------------------------
class ValidationException(BaseAPIException):
    def __init__(self, detail: str, error_code: str = "1400"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code,
        )


class PasswordValidationException(ValidationException):
    def __init__(self):
        super().__init__(
            "Пароль должен содержать минимум 8 символов и хотя бы одну цифру",
            error_code="1401",
        )


# --------------------------------------------------
# Операции (15xx)
# --------------------------------------------------
class OperationException(BaseAPIException):
    def __init__(self, status_code: int, detail: str, error_code: str):
        super().__init__(status_code, detail, error_code)


class DeleteException(OperationException):
    def __init__(self, detail: str = "Ошибка при удалении"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="1501",
        )


class LastContactDeleteException(DeleteException):
    def __init__(self):
        super().__init__("Невозможно удалить единственный контакт")


class UpdateException(OperationException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении",
            error_code="1502",
        )


class CreateException(OperationException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при создании",
            error_code="1503",
        )


class DuplicateEntryException(OperationException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Запись уже существует",
            error_code="1504",
        )


# --------------------------------------------------
# Доступ (16xx)
# --------------------------------------------------
class ForbiddenException(BaseAPIException):
    def __init__(self, detail: str = "Доступ запрещен"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN, detail=detail, error_code="1600"
        )
