# app/db/models/user.py

import secrets
from datetime import datetime, UTC, timedelta, timezone
from typing import List, TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Enum as SqlEnum, TIMESTAMP, String, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .enums import RoleEnum, GenderEnum, TokenTypeEnum
from .base_sql import (IntIdSQL, UuIdSQL, str_1000_null_false, expires_at, str_255_uniq_null_true,
                       str_255_uniq_null_false, bool_false, str_1000_null_true, str_255_null_true)

if TYPE_CHECKING:
    from .associations import UserRole


class User(IntIdSQL):
    __tablename__ = 'users'

    phone_number: Mapped[str_255_uniq_null_true]
    email: Mapped[str_255_uniq_null_false]
    password: Mapped[str]
    is_banned: Mapped[bool_false] # заблокирован
    is_email_confirmed: Mapped[bool_false] # подтвержден ли адрес электронной почты
    is_phone_confirmed: Mapped[bool_false] # подтвержден ли номер телефона
    ban_until: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True) # запрещать до тех пор, пока
    last_login_attempt: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True) # последняя попытка входа в систему
    failed_attempts: Mapped[int] = mapped_column(default=0) # кол-во неудачных попыток

    profile_id: Mapped[int | None] = mapped_column(ForeignKey('profiles.id'))
    profile: Mapped["Profile"] = relationship(
        "Profile",
        uselist=False,  # Отношение "один к одному"
        lazy="selectin",  # Загружается сразу с User
        passive_deletes=True,  # Использует 'ondelete' в БД для удаления
        back_populates="user",
    )

    roles: Mapped[List['UserRole']] = relationship(
        "UserRole",
        cascade="all, delete-orphan",
        lazy="selectin",
        back_populates='user',
    )

    tokens: Mapped[List["Token"]] = relationship(
        "Token",
        cascade="all, delete-orphan",
        back_populates="user",
    )

    devices: Mapped[List["Device"]] = relationship(
        "Device",
        cascade="all, delete-orphan",
        back_populates="user"
    )



    # ??? НАДО УТОЧНИТЬ
    #⚠️ Это никогда не вызовется, если ты не используешь dataclasses — SQLAlchemy ORM игнорирует __post_init__.

    @property
    def is_expired(self):
        return datetime.now(UTC) > self.ban_until

    def __post_init__(self):
        if self.is_expired:
            self.ban_until = False


    def __repr__(self):
        ban_info = f", ban_until={self.ban_until.strftime('%Y-%m-%d %H:%M:%S')}" if self.ban_until else ""
        return f"{self.__class__.__name__}(id={self.id}, is_banned={self.is_banned}{ban_info})"

    def __str__(self):
        return f"{self.email or 'Пользователь'} (id={self.id})"

class Device(UuIdSQL):
    __tablename__ = "devices"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_agent: Mapped[str_1000_null_true]
    ip_address: Mapped[str_255_null_true]
    name: Mapped[str_255_null_true]
    is_active: Mapped[bool_false]
    last_used_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="devices")


    def __str__(self):
        return f"{self.name or 'Устройство'} | {self.user_agent or 'UA неизвестен'}"

class Token(UuIdSQL):
    __tablename__ = 'tokens'

    token: Mapped[str_1000_null_false] = mapped_column(unique=True)
    token_type: Mapped[TokenTypeEnum] = mapped_column(SqlEnum(TokenTypeEnum, name="token_type_enum"))
    expires_at: Mapped[expires_at]
    ban: Mapped[bool_false]

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship(back_populates="tokens")
    device: Mapped["Device"] = relationship()


    @property
    def is_expired(self):
        return datetime.now(UTC) > self.expires_at

    # ??? НАДО УТОЧНИТЬ
    #⚠️ Это никогда не вызовется, если ты не используешь dataclasses — SQLAlchemy ORM игнорирует __post_init__.

    def __post_init__(self):
        if self.is_expired:
            self.ban = True

    def __repr__(self):
        return (f"<Token(id={self.id}, user_id={self.user_id}, device_id={self.device_id}, "
                f"type={self.token_type}, expires_at={self.expires_at}, ban={self.ban})>")

    def __str__(self):
        return f"Token до {self.expires_at.date()} — {'заблокирован' if self.ban else 'активен'}"



class Profile(UuIdSQL):
    __tablename__ = 'profiles'

    first_name: Mapped[str | None]
    last_name: Mapped[str | None]
    data_birth: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    gender: Mapped[GenderEnum] = mapped_column(SqlEnum(GenderEnum, name="gender_enum"), nullable=False,
                                               default=GenderEnum.NOT_SPECIFIED, comment="Пол пользователя")

    user: Mapped["User"] = relationship(
        "User",
        uselist=False,
        lazy="selectin",  # Оптимизация загрузки профиля для списка пользователей
        passive_deletes=True,
        back_populates="profile"
    )

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id})"

    def __str__(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()



class Role(UuIdSQL):
    __tablename__ = 'roles'

    name: Mapped[RoleEnum] = mapped_column(SqlEnum(RoleEnum, name="role_enum"), primary_key=True, unique=True)
    users: Mapped[List['UserRole']] = relationship(
        "UserRole",
        back_populates="role"
    )

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name})"

    def __str__(self):
        return self.name


class EmailVerificationToken(UuIdSQL):
    __tablename__ = 'email_verification_tokens'

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str_255_uniq_null_false]
    ban: Mapped[bool_false]
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


    def __init__(self, email: str, **kw: Any):
        super().__init__(**kw)
        self.email = email
        self.token = secrets.token_urlsafe(32)  # Генерация уникального токена
        self.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id})"

    def __str__(self):
        return f"Токен для {self.email} до {self.expires_at.date()}"


class ChangeEmailVerificationToken(UuIdSQL):
    __tablename__ = 'change_email_verification_tokens'

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    new_email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str_255_uniq_null_false]
    ban: Mapped[bool_false]
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


    def __init__(self, email: str, **kw: Any):
        super().__init__(**kw)
        self.email = email
        self.token = secrets.token_urlsafe(32)  # Генерация уникального токена
        self.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id})"

    def __str__(self):
        return f"Токен для {self.email} до {self.expires_at.date()}"


class ResetPasswordToken(UuIdSQL):
    __tablename__ = 'reset_password_tokens'

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str_255_uniq_null_false]
    ban: Mapped[bool_false]
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


    def __init__(self, email: str, **kw: Any):
        super().__init__(**kw)
        self.email = email
        self.token = secrets.token_urlsafe(32)  # Генерация уникального токена
        self.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id})"

    def __str__(self):
        return f"Токен для {self.email} до {self.expires_at.date()}"



# автоматически перед flush (через SQLAlchemy events)
# Если хочешь, чтобы всегда обновлялся ban, когда токен устарел:

# @event.listens_for(Token, "before_update", propagate=True)
# def auto_ban_expired_token(mapper, connection, target: Token):
#     if target.is_expired and not target.ban:
#         target.ban = True