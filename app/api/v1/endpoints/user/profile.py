# app/api/v1/endpoints/user/profile.py

from typing import TYPE_CHECKING

from fastapi import APIRouter, Security
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import UserNotFoundException, UpdateException
from app.core.responses import profile_get_resps, profile_put_resps
from app.core.security.auth import get_current_user
from app.db.models import User, Profile
from app.db.sessions import SessionDep, TransactionSessionDep
from app.utils.logger import logger
from app.db.schemas.user import ProfileInfo

if TYPE_CHECKING:
    from app.db.schemas.user import ProfileModel


profile_router = APIRouter(prefix="/me/profile", tags=["Me Profile"])


@profile_router.get("", responses=profile_get_resps)
async def get_me_profile(
    db: SessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
) -> ProfileInfo:
    """
    ## Endpoint запроса данных профиля пользователя системы.

    ### Описание
    - Возвращает данные профиля пользователя сделавшего запрос.
    - Endpoint доступен для всех авторизовавшихся пользователей.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    if user_data is None:
        logger.remove()
        raise UserNotFoundException
    profile_dict = user_data.profile.to_dict_one_lap()
    profile_dict["user_id"] = user_data.id
    profile = ProfileInfo(**profile_dict)
    return profile


@profile_router.put("", responses=profile_put_resps)
async def put_me_profile(
    schema: ProfileModel,
    db: TransactionSessionDep,
    user_data: User = Security(get_current_user, scopes=["USER"]),
) -> ProfileInfo:
    """
    ## Endpoint обновления профиля пользователя системы.

    ### Описание
    - Endpoint обновляет профиль пользователя
    - Endpoint доступен для всех авторизовавшихся пользователей.
    - Возвращает данные пользователя сделавшего запрос.

    ### Требования
    - Этот эндпоинт не требует передачи данных в теле запроса.
    - Пользователь должен быть авторизован (наличие токена в cookie-файле).
    """

    if user_data is None:
        logger.remove()
        raise UserNotFoundException

    # Явно загружаем пользователя в текущую сессию
    user = await db.get(User, user_data.id)
    if not user:
        logger.remove()
        raise UserNotFoundException

    profile_dict = schema.model_dump(exclude_none=True)

    try:
        if user.profile is None:
            new_profile = Profile(**profile_dict)
            db.add(new_profile)
            await db.flush()
            user.profile_id = new_profile.id
            # Явно добавляем пользователя в сессию для обновления
            db.add(user)
        else:
            for key, value in profile_dict.items():
                setattr(user.profile, key, value)

        await db.commit()  # Фиксируем изменения
        await db.refresh(user)  # Теперь refresh будет работать

        profile_dict = user.profile.to_dict_one_lap()
        profile_dict["user_id"] = user.id
        return ProfileInfo(**profile_dict)

    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Ошибка при обновлении профиля пользователя {user.id}: {e}")
        raise UpdateException
