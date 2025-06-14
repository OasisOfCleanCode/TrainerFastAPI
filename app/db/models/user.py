import secrets
from datetime import datetime, UTC, timedelta, timezone
from typing import List, TYPE_CHECKING, Any

from sqlalchemy import BigInteger, ForeignKey, Enum as SqlEnum, TIMESTAMP, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .enums import RoleEnum, GenderEnum, TokenTypeEnum
from .base_sql import (BaseSQL, AbstractBaseSQL,
                        str_1000_null_false, expires_at, str_255_uniq_null_true,
                        str_255_uniq_null_false, bool_false)
from ...core.exceptions import ValidationException

if TYPE_CHECKING:
    from .associations import UserRole


class User(BaseSQL):
    __tablename__ = 'users'

    phone_number: Mapped[str_255_uniq_null_true]
    email: Mapped[str_255_uniq_null_false]
    password: Mapped[str]
    is_banned: Mapped[bool_false] # заблокирован
    is_email_confirmed: Mapped[bool_false] # подтвержден ли адрес электронной почты
    is_phone_confirmed: Mapped[bool_false]
    ban_until: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True) # запрещать до тех пор, пока
    last_login_attempt: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True) # последняя попытка входа в систему
    failed_attempts: Mapped[int] = mapped_column(default=0)

    profile_id: Mapped[int | None] = mapped_column(ForeignKey('profiles.id'))
    profile: Mapped["Profile"] = relationship(
        "Profile",
        uselist=False,  # Отношение "один к одному"
        lazy="selectin",  # Загружается сразу с User
        passive_deletes=True,  # Использует 'ondelete' в БД для удаления
        back_populates="user",
    )

    services_assoc: Mapped[List['Service']] = relationship(
        "Service",
        cascade="all, delete-orphan",
        back_populates="user",
    )

    roles_assoc: Mapped[List['UserRole']] = relationship(
        "UserRole",
        cascade="all, delete-orphan",
        lazy="selectin",
        back_populates='user',
    )

    access_token_assoc: Mapped[List["Token"]] = relationship(
        "Token",
        uselist=True,
        cascade="all, delete-orphan",
        back_populates="access_token_user",
        primaryjoin="and_(Token.user_id==User.id, Token.ban==False, Token.token_type=='ACCESS')",
        overlaps="refresh_token_assoc,access_token_user,refresh_token_user"  # ✅ Полное перекрытие
    )

    refresh_token_assoc: Mapped[List["Token"]] = relationship(
        "Token",
        uselist=True,
        cascade="all, delete-orphan",
        back_populates="refresh_token_user",
        primaryjoin="and_(Token.user_id==User.id, Token.ban==False, Token.token_type=='REFRESH')",
        overlaps="access_token_assoc,refresh_token_user,access_token_user"  # ✅ Полное перекрытие
    )

    @property
    def is_expired(self):
        return datetime.now(UTC) > self.ban_until

    def __post_init__(self):
        if self.is_expired:
            self.ban_until = False

    @property
    def roles(self):
        return [user_role.role_name for user_role in self.roles_assoc]

    @property
    def access_token(self):
        # Возвращаем токен доступа
        for token in self.access_token_assoc:
            if not token.ban and token.token_type == TokenTypeEnum.ACCESS:
                return token.token
        else:
            return None

    @property
    def refresh_token(self):
        # Возвращаем refresh токен
        for token in self.refresh_token_assoc:
            if not token.ban and token.token_type == TokenTypeEnum.REFRESH:
                return token.token
        else:
            return None

    def __repr__(self):
        ban_info = f", ban_until={self.ban_until.strftime('%Y-%m-%d %H:%M:%S')}" if self.ban_until else ""
        return f"{self.__class__.__name__}(id={self.id}, is_banned={self.is_banned}{ban_info})"


class Service(BaseSQL):
    __tablename__ = 'services'

    provider: Mapped[str]
    provider_user_id: Mapped[str]
    email: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user: Mapped['User'] = relationship(
        "User",
        lazy="selectin",
        back_populates="services_assoc",
    )

    access_token_assoc: Mapped[List["Token"]] = relationship(
        "Token",
        uselist=True,
        back_populates="access_token_service",
        primaryjoin="and_(Token.service_id==Service.id, Token.ban==False, Token.token_type=='ACCESS')",
        overlaps="refresh_token_assoc,access_token_service,refresh_token_service"  # ✅ Полное перекрытие
    )

    refresh_token_assoc: Mapped[List["Token"]] = relationship(
        "Token",
        uselist=True,
        back_populates="refresh_token_service",
        primaryjoin="and_(Token.service_id==Service.id, Token.ban==False, Token.token_type=='REFRESH')",
        overlaps="access_token_assoc,refresh_token_service,access_token_service"  # ✅ Полное перекрытие
    )

    @property
    def access_token(self):
        # Возвращаем токен доступа
        for token in self.access_token_assoc:
            if not token.ban and token.token_type == TokenTypeEnum.ACCESS:
                return token.token
        else:
            return None


    @property
    def refresh_token(self):
        # Возвращаем refresh токен
        for token in self.refresh_token_assoc:
            if not token.ban and token.token_type == TokenTypeEnum.ACCESS:
                return token.token
        else:
            return None

    def __repr__(self):
        return (f"{self.__class__.__name__}(id={self.id}, client={self.user_id}, "
                f"provider={self.provider})")


class Token(BaseSQL):
    __tablename__ = 'tokens'

    token: Mapped[str_1000_null_false] = mapped_column(unique=True)
    token_type: Mapped[TokenTypeEnum] = mapped_column(SqlEnum(TokenTypeEnum, name="token_type_enum"),
                                                      nullable=False, comment="Тип токена: ACCESS или REFRESH")
    expires_at: Mapped[expires_at]
    ban: Mapped[bool_false]
    issued_by_admin_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"),
                                                           comment="ID администратора, использовавшего токен")

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))

    access_token_user: Mapped['User'] = relationship(
        "User",
        lazy="selectin",
        back_populates="access_token_assoc",
        foreign_keys=[user_id],
        overlaps="refresh_token_user,access_token_assoc,refresh_token_assoc"  # ✅ Полное перекрытие
    )

    refresh_token_user: Mapped['User'] = relationship(
        "User",
        lazy="selectin",
        back_populates="refresh_token_assoc",
        foreign_keys=[user_id],
        overlaps="access_token_user,refresh_token_assoc,access_token_assoc"  # ✅ Полное перекрытие
    )

    access_token_service: Mapped['Service'] = relationship(
        "Service",
        lazy="selectin",
        back_populates="access_token_assoc",
        foreign_keys=[service_id],
        overlaps="refresh_token_service,access_token_assoc,refresh_token_assoc"  # ✅ Полное перекрытие
    )

    refresh_token_service: Mapped['Service'] = relationship(
        "Service",
        lazy="selectin",
        back_populates="refresh_token_assoc",
        foreign_keys=[service_id],
        overlaps="access_token_service,refresh_token_assoc,access_token_assoc"  # ✅ Полное перекрытие
    )

    @validates('client_id', 'service_id')
    def validate_exclusive_ids(self, key, value):
        if self.user_id and self.service_id:
            raise ValidationException("Только одно из полей client_id или service_id должно быть заполнено.")
        if not self.user_id and not self.service_id:
            raise ValidationException("Должно быть заполнено одно из полей: client_id или service_id.")
        return value

    @property
    def is_expired(self):
        return datetime.now(UTC) > self.expires_at

    def __post_init__(self):
        if self.is_expired:
            self.ban = True

    def __repr__(self):
        title_id = f'user_id={self.user_id}' if self.user_id else f'service_id={self.service_id}'
        adm = f', issued_by_admin_id={self.issued_by_admin_id}' if self.issued_by_admin_id else ''
        return f"{self.__class__.__name__}({title_id}, expires_at={self.expires_at}, ban={self.ban}{adm})"


class Profile(BaseSQL):
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
        return f"{self.__class__.__name__}(id={self.id}"


class BodyMeasurements(BaseSQL):
    __tablename__ = 'body_measurements'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Верхняя часть тела
    shoulder: Mapped[float | None]  # плечи (ширина)
    neck: Mapped[float | None]  # шея
    bust_height: Mapped[float | None]  # высота груди (от плеча до соска)
    shoulder_to_waist_front: Mapped[float | None]  # плечо до талии (спереди)
    bust_separation: Mapped[float | None]  # расстояние между сосками
    bust: Mapped[float | None]  # грудь (обхват)
    under_bust: Mapped[float | None]  # под грудью (обхват)
    l_bicep: Mapped[float | None]  # левый бицепс
    r_bicep: Mapped[float | None]  # правый бицепс

    # Торс и талия
    waist: Mapped[float | None]  # талия
    hip_height: Mapped[float | None]  # высота бедра (от талии до тазобедренного сустава)
    hips: Mapped[float | None]  # бёдра (обхват)
    abdomen: Mapped[float | None]  # живот (если отличен от талии)

    # Руки
    l_wrist: Mapped[float | None]  # левое запястье
    r_wrist: Mapped[float | None]  # правое запястье
    arm_length: Mapped[float | None]  # длина руки (от плеча до запястья)

    # Ноги
    l_thigh: Mapped[float | None]  # левое бедро
    r_thigh: Mapped[float | None]  # правое бедро
    l_calf: Mapped[float | None]  # левая голень
    r_calf: Mapped[float | None]  # правая голень

    # Спина
    shoulder_to_waist_back: Mapped[float | None]  # плечо до талии (сзади)
    back_width: Mapped[float | None]  # ширина спины

    # Рост
    waist_to_floor: Mapped[float | None]  # от талии до пола
    leg_length: Mapped[float | None]  # длина ноги
    neck_to_floor: Mapped[float | None]  # от шеи до пола
    total_height: Mapped[float | None]  # полный рост

    # Вес
    weight: Mapped[float | None] # Вес



class Role(AbstractBaseSQL):
    __tablename__ = 'roles'

    name: Mapped[RoleEnum] = mapped_column(SqlEnum(RoleEnum, name="role_enum"), primary_key=True, unique=True)
    users_assoc: Mapped[List['UserRole']] = relationship(
        "UserRole",
        back_populates="role"
    )

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name})"


class EmailVerificationToken(BaseSQL):
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
        return f"{self.__class__.__name__}(id={self.id}"


class ChangeEmailVerificationToken(BaseSQL):
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
        return f"{self.__class__.__name__}(id={self.id}"


class ResetPasswordToken(BaseSQL):
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
        return f"{self.__class__.__name__}(id={self.id}"


