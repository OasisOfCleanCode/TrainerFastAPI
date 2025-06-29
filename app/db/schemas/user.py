import re
from datetime import datetime
from typing import Self, List, Union, Optional

from fastapi.params import Form
from app.utils.logger import logger
from pydantic import Field, EmailStr, field_validator, model_validator, computed_field

from app.core.exceptions import ValidationException, PasswordValidationException
from app.db.models.enums import RoleEnum, BanTimeEnum, GenderEnum, TokenTypeEnum
from app.db.schemas.base_schemas import _BaseSchema


class PhoneOrEmailModel(_BaseSchema):
    phone_or_email: str = Field(
        ..., description="Идентификатор объекта (номер телефона или email)"
    )

    @field_validator("phone_or_email")
    def validate_identifier(value: str) -> str:
        """
        Проверка, что идентификатор является либо email, либо номером телефона.
        """
        is_email = None
        is_phone = re.match(r"^\+?[1-9]\d{1,14}$", value)
        try:
            is_email = EmailStr._validate(value)
        except ValidationException("Адрес Email некорректный"):
            pass

        if not (is_email or is_phone):
            raise ValidationException(
                "Идентификатор должен быть либо email, либо номером телефона."
            )
        return value

    @computed_field
    @property
    def phone_number(self) -> Optional[str]:
        """
        Возвращает номер телефона, если идентификатор является валидным номером телефона.
        """
        if re.match(r"^\+?[1-9]\d{1,14}$", self.phone_or_email):
            digits = "".join(re.findall(r"\d+", self.phone_or_email))
            if digits.startswith("8"):
                self.phone_or_email = f"+7{digits[1:]}"
            elif digits.startswith("7"):
                self.phone_or_email = f"+{digits}"
            else:
                self.phone_or_email = f"+7{digits}"
            return self.phone_or_email
        return self

    @computed_field
    @property
    def email(self) -> Optional[str]:
        """
        Возвращает email, если идентификатор является валидным email.
        """
        try:
            return EmailStr._validate(self.phone_or_email)
        except ValidationException("Адрес Email некорректный"):
            return None


class CheckIDModel(_BaseSchema):
    id: int = Field(description="Идентификатор")


class CheckUserIDModel(_BaseSchema):
    user_id: int = Field(description="Идентификатор пользователя")


class CheckEmailModel(_BaseSchema):
    email: EmailStr = Field(description="Электронная почта")

    @field_validator("email")
    def validate_email(value: str) -> str:
        if value:
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value):
                raise ValidationException(
                    "Email должен соответствовать формату электронной почты"
                )
        return value


class CheckPhoneModel(_BaseSchema):
    phone_number: str = Field(
        description="Номер телефона в международном формате, начинающийся с '+'"
    )

    @field_validator("phone_number")
    def validate_phone_number(value: str) -> str:
        if value:
            pattern = r"^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$"
            if not re.match(pattern, value):
                raise ValidationException(
                    'Номер телефона должен начинаться с "+" и содержать от 5 до 15 цифр'
                )
        return value

    @property
    def formatted_phone_number(self) -> str | None:
        if self.phone_number:
            digits = "".join(re.findall(r"\d+", self.phone_number))
            if digits.startswith("8"):
                self.phone_number = f"+7{digits[1:]}"
            elif digits.startswith("7"):
                self.phone_number = f"+{digits}"
            else:
                self.phone_number = f"+7{digits}"
        return self


class CheckRoleModel(_BaseSchema):
    role: RoleEnum = Field(
        default="USER", description="Укажите право доступа. Например: USER"
    )


class CheckTokenModel(_BaseSchema):
    token: str = Field(..., description="Токен")


class CheckTimeBan(_BaseSchema):
    period: BanTimeEnum = Field(..., description="Время блокировки")


class CheckPassword(_BaseSchema):
    password: str = Field(
        min_length=5, max_length=50, description="Пароль, от 5 до 50 знаков"
    )
    confirm_password: str = Field(
        min_length=5, max_length=50, description="Повторите пароль"
    )

    @model_validator(mode="after")
    def check_password(self) -> Self:
        if self.password != self.confirm_password:
            raise ValidationException("Пароли не совпадают")
        self.password = self.get_password_hash(
            self.password
        )  # хешируем пароль до сохранения в базе данных
        return self

    @field_validator("password")
    def validate_password(value: str) -> str:
        if value:
            val_pass = re.match(r"^(?=.*[0-9])[a-zA-Z0-9]{8,}$", value)
            if not val_pass:
                logger.remove()
                raise PasswordValidationException
        return value

    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Хэширование пароля для сохранения в базе данных.

        :param password: Обычный пароль пользователя.
        :return: Хэшированный пароль.
        """
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash(password)
        logger.info("Пароль успешно хэширован")
        return hashed_password


class ResetPasswordSchema(CheckPassword):
    token: str = Form(..., description="Токен восстановления пароля")
    password: str = Form(
        min_length=5, max_length=50, description="Пароль, от 5 до 50 знаков"
    )
    confirm_password: str = Form(
        min_length=5, max_length=50, description="Повторите пароль"
    )

    @model_validator(mode="after")
    def check_password(self) -> Self:
        if self.password != self.confirm_password:
            raise ValidationException("Пароли не совпадают")
        self.password = self.get_password_hash(
            self.password
        )  # хешируем пароль до сохранения в базе данных
        return self

    @field_validator("password")
    def validate_password(value: str) -> str:
        if value:
            val_pass = re.match(r"^(?=.*[0-9])[a-zA-Z0-9]{8,}$", value)
            if not val_pass:
                logger.remove()
                raise PasswordValidationException
        return value

    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Хэширование пароля для сохранения в базе данных.

        :param password: Обычный пароль пользователя.
        :return: Хэшированный пароль.
        """
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash(password)
        logger.info("Пароль успешно хэширован")
        return hashed_password

    @classmethod
    def as_form(
        cls,
        token: str = Form(...),
        password: str = Form(...),
        confirm_password: str = Form(...),
    ) -> "ResetPasswordSchema":
        return cls(token=token, password=password, confirm_password=confirm_password)


class IDModel(CheckIDModel):
    id: int | None = Field(default=None, description="Идентификатор")


class UserIDModel(CheckUserIDModel):
    user_id: int | None = Field(default=None, description="Идентификатор пользователя")


class EmailModel(CheckEmailModel):
    email: EmailStr | None = Field(default=None, description="Электронная почта")


class PhoneModel(CheckPhoneModel):
    phone_number: str | None = Field(
        default=None,
        description="Номер телефона в международном формате, начинающийся с '+'",
    )

    @property
    def formatted_phone_number(self) -> str | None:
        if self.phone_number:
            digits = "".join(re.findall(r"\d+", self.phone_number))
            if digits.startswith("8"):
                return f"+7{digits[1:]}"
            elif digits.startswith("7"):
                return f"+{digits}"
            else:
                return f"+7{digits}"
        return self


class RoleModel(_BaseSchema):
    role: RoleEnum = Field(..., description="Укажите право доступа. Например: USER")


class EmailPhoneModel(EmailModel, PhoneModel):

    @model_validator(mode="before")
    def check_email_or_phone(values):
        if isinstance(values, dict):
            email = values.get("email")
            phone_number = values.get("phone_number")

            if not email and not phone_number:
                raise ValidationException(
                    "Должно быть указано хотя бы одно из полей: email или номер телефона."
                )
        return values


class IDEmailPhoneModel(EmailModel, PhoneModel, IDModel):

    @model_validator(mode="before")
    def check_email_or_phone(values):
        if isinstance(values, dict):
            email = values.get("email")
            phone_number = values.get("phone_number")
            id = values.get("id")

            if not email and not phone_number and not id:
                raise ValidationException(
                    "Должно быть указано хотя бы одно из полей: id, email или номер телефона."
                )
        return values


class IDEmailPhoneRoleModel(IDEmailPhoneModel, RoleModel):
    pass


class ProfileModel(_BaseSchema):
    first_name: str | None = Field(
        None, min_length=3, max_length=50, description="Имя, от 3 до 50 символов"
    )
    last_name: str | None = Field(
        None, min_length=3, max_length=50, description="Фамилия, от 3 до 50 символов"
    )
    data_birth: datetime | None = Field(None, description="Дата рождения")
    gender: GenderEnum = Field(GenderEnum.NOT_SPECIFIED, description="Пол пользователя")


class ProfileInfo(ProfileModel, CheckIDModel, CheckUserIDModel):
    pass


class SUserRegister(CheckPassword, EmailPhoneModel):
    pass


class SUserRefreshPassword(_BaseSchema):

    password: str = Field(min_length=5, max_length=50, description="Старый пароль.")
    new_password: str = Field(
        min_length=5, max_length=50, description="Пароль, от 5 до 50 знаков"
    )
    confirm_new_password: str = Field(
        min_length=5, max_length=50, description="Повторите пароль"
    )

    @model_validator(mode="after")
    def check_password(self) -> Self:
        if self.new_password != self.confirm_new_password:
            raise ValidationException("Пароли не совпадают")
        self.new_password = self.get_password_hash(
            self.new_password
        )  # хешируем пароль до сохранения в базе данных
        return self

    @field_validator("new_password")
    def validate_password(value: str) -> str:
        if value:
            val_pass = re.match(r"^(?=.*[0-9])[a-zA-Z0-9]{8,}$", value)
            if not val_pass:
                logger.remove()
                raise PasswordValidationException
        return value

    @staticmethod
    def get_password_hash(new_password: str) -> str:
        """
        Хэширование пароля для сохранения в базе данных.

        :return: Хэшированный пароль.
        """
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash(new_password)
        logger.info("Пароль успешно хэширован")
        return hashed_password


class SUserAddDB(EmailPhoneModel):
    password: str = Field(min_length=5, description="Пароль в формате HASH-строки")


class SUserAuth(EmailPhoneModel):
    password: str = Field(
        min_length=5, max_length=50, description="Пароль, от 5 до 50 знаков"
    )


class SRoleInfo(_BaseSchema):
    roles: Optional[list[RoleEnum | str]] = Field(
        default=[], description="Права доступа."
    )


class SUserInfo(IDEmailPhoneModel):
    is_email_confirmed: bool
    is_banned: bool
    ban_until: Optional[datetime]
    last_login_attempt: Optional[datetime]
    failed_attempts: int
    profile: Optional["ProfileModel"]


class SUserInfoRole(SRoleInfo, SUserInfo):
    pass


class TokenModel(_BaseSchema):
    token: str = Field(description="Refresh Токен")
    token_type: TokenTypeEnum = Field(description="Тип токена")


class TokenBase(TokenModel):
    user_id: int | None = Field(None, description="Идентификатор пользователя")
    service_id: int | None = Field(None, description="Идентификатор сервиса")
    expires_at: datetime

    @model_validator(mode="before")
    def check_user_or_service(values):
        if isinstance(values, dict):
            service_id = values.get("service_id")
            user_id = values.get("user_id")

            if not user_id and not service_id:
                raise ValidationException(
                    "Должно быть указано хотя бы одно из полей: user_id или service_id."
                )
        return values


class TokenInfo(TokenBase):
    created_at: datetime
    updated_at: datetime
    ban: bool


class ErrorValidResponseSchema(_BaseSchema):
    detail: str


class ErrorResponseSchema(_BaseSchema):
    status: str = Field("error", examples=["error"])
    message: str
    error_code: Union[int, None] = Field(
        default=None, examples=[1001, 1002, 1003, 1004, 9999]
    )  # Пример с кодом ошибки


class SuccessfulResponseSchema(_BaseSchema):
    status: str = Field("success", examples=["success"])
    message: str


class SuccessfulResponseDataSchema(SuccessfulResponseSchema):
    data: Union[dict, None] = None


class ServerErrorResponseSchema(_BaseSchema):
    status: str = Field("error", examples=["error"])
    message: str
    error_code: Union[int, None] = Field(
        default=None, examples=["1006"]
    )  # Пример с кодом ошибки


class AccessTokenSchema(_BaseSchema):
    access_token: str = Field(None, examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"])
    token_type: str = Field("bearer", examples=["bearer"])


class ValidationErrorDetail(_BaseSchema):
    loc: List[Union[str, int]]  # Путь к полю с ошибкой
    msg: str  # Сообщение об ошибке
    type: str  # Тип ошибки


class ValidationResponseSchema(_BaseSchema):
    detail: List[ValidationErrorDetail]
    error_code: Union[int, None] = Field(
        default=None, examples=["9999"]
    )  # Пример с кодом ошибки для валидации


class ValidErrorExceptionSchema(_BaseSchema):
    detail: str
    error_code: Union[int, None] = Field(
        default=None, examples=["1005"]
    )  # Пример с кодом ошибки для валидации


class AvailableExceptionSchema(_BaseSchema):
    detail: str
    success_code: Union[int, None] = Field(
        default=None, examples=["2004", "2005"]
    )  # Пример с кодом ошибки для валидации
