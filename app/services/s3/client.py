import asyncio
import errno
import mimetypes
import os
from datetime import datetime
from io import BytesIO
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from minio import Minio
from minio.error import S3Error
from config import MINIO_HOST, MINIO_PORT, MINIO_USER, MINIO_PASS, MINIO_CATALOG_NAME, BASE_PHOTO_PATH
from app.utils.logger import loggerfrom fastapi.responses import StreamingResponse
from fastapi import HTTPException


class S3Client:
    """
    Асинхронный клиент для работы с S3 (MinIO) или локальным хранилищем (по флагу use_s3).
    """

    def __init__(self, use_s3: bool = True):
        self.use_s3 = use_s3
        endpoint = f"{MINIO_HOST}:{MINIO_PORT}"
        self.client = Minio(
            endpoint,
            access_key=MINIO_USER,
            secret_key=MINIO_PASS,
            secure=False
        )
        self.bucket_name = MINIO_CATALOG_NAME
        logger.info(f"S3Client инициализирован с endpoint: {endpoint}, bucket: {self.bucket_name}, use_s3: {self.use_s3}")

    @staticmethod
    async def validate_image_file(file_bytes: bytes, filename: str) -> bool:
        size_mb = len(file_bytes) / (1024 * 1024)
        logger.info(f"Проверка файла {filename}, размер: {size_mb:.2f} MB")
        if size_mb > 10:
            logger.warning(f"Файл {filename} превышает лимит 10 МБ")
            return False
        try:
            await asyncio.to_thread(lambda: Image.open(BytesIO(file_bytes)).verify())
            logger.info(f"Файл {filename} - изображение")
            return True
        except UnidentifiedImageError:
            logger.warning(f"Файл {filename} не является изображением")
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке файла {filename}: {e}")
            return False

    @staticmethod
    async def convert_to_webp(file_bytes: bytes, quality: int = 80) -> bytes:
        logger.info("Начало конвертации в WebP")
        try:
            def _convert():
                with Image.open(BytesIO(file_bytes)) as img:
                    img = img.convert("RGB")
                    output = BytesIO()
                    img.save(output, format="WEBP", quality=quality)
                    return output.getvalue()

            webp_bytes = await asyncio.to_thread(_convert)
            logger.info(f"Конвертация завершена. Размер: {len(webp_bytes)/1024:.2f} KB")
            return webp_bytes
        except Exception as e:
            logger.error(f"Ошибка при конвертации: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при конвертации в WebP")

    @staticmethod
    async def resize_and_crop(image: Image.Image, min_side=64) -> Image.Image:
        logger.info("Уменьшение изображения")
        try:
            width, height = image.size
            scale = min_side / min(width, height)
            new_size = (int(width * scale), int(height * scale))
            resized_image = await asyncio.to_thread(
                lambda: image.resize(new_size, Image.Resampling.LANCZOS)
            )
            logger.info(f"Изображение уменьшено до: {new_size}")
            return resized_image
        except Exception as e:
            logger.error(f"Ошибка при уменьшении: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при уменьшении изображения")

    async def upload_and_prepare_images(self, photo_id: str, orig_file_bytes: bytes, date: datetime) -> tuple[str, str]:
        logger.info(f"Подготовка и загрузка изображения: {photo_id}")
        try:
            orig_webp_bytes = await self.convert_to_webp(orig_file_bytes)
            with Image.open(BytesIO(orig_file_bytes)) as img:
                img = img.convert("RGB")
                preview_img = await self.resize_and_crop(img)
                output = BytesIO()
                await asyncio.to_thread(preview_img.save, output, "WEBP", quality=80)
                preview_webp_bytes = output.getvalue()
                logger.info("Превью успешно создано")

            if self.use_s3:
                return await self.upload_photo_and_preview(photo_id, orig_webp_bytes, preview_webp_bytes, date)
            else:
                return await self.local_upload_photo_and_preview(photo_id, orig_webp_bytes, preview_webp_bytes, date)
        except HTTPException as e:
            logger.error(f"HTTPException: {e.detail}")
            raise e
        except Exception as e:
            logger.error(f"Ошибка при подготовке и загрузке: {e}")
            raise HTTPException(status_code=500, detail="Неизвестная ошибка при подготовке и загрузке")

    @classmethod
    async def upload_photo_and_preview(photo_id: str, orig_file_bytes: bytes, preview_file_bytes: bytes, date: datetime) -> tuple[str, str]:
        logger.info("Загрузка файлов в S3")
        date_str = date.strftime("%Y-%m-%d")
        orig_key = f"{date_str}/{photo_id}/orig.webp"
        preview_key = f"{date_str}/{photo_id}/preview.webp"

        try:
            await asyncio.to_thread(cls().client.put_object, cls().bucket_name, orig_key, BytesIO(orig_file_bytes), len(orig_file_bytes), "image/webp")
            logger.info(f"Оригинальное изображение {orig_key} успешно загружено в S3")
        except S3Error as e:
            logger.error(f"S3Error при загрузке {orig_key}: {e}")
            raise HTTPException(status_code=500, detail=f"S3 ошибка: {e.code}")
        except Exception as e:
            logger.error(f"Ошибка при загрузке {orig_key}: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при загрузке оригинала в S3")

        try:
            await asyncio.to_thread(cls().client.put_object, cls().bucket_name, preview_key, BytesIO(preview_file_bytes), len(preview_file_bytes), "image/webp")
            logger.info(f"Превью {preview_key} успешно загружено в S3")
        except S3Error as e:
            logger.error(f"S3Error при загрузке превью {preview_key}: {e}")
            raise HTTPException(status_code=500, detail=f"S3 ошибка: {e.code}")
        except Exception as e:
            logger.error(f"Ошибка при загрузке превью {preview_key}: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при загрузке превью в S3")

        return orig_key, preview_key

    @classmethod
    async def local_upload_photo_and_preview(photo_id: str, orig_file_bytes: bytes, preview_file_bytes: bytes, date: datetime) -> tuple[str, str]:
        logger.info("Загрузка файлов локально")
        date_str = date.strftime("%Y-%m-%d")
        orig_key = f"{date_str}/{photo_id}/orig.webp"
        preview_key = f"{date_str}/{photo_id}/preview.webp"
        orig_path = os.path.join(BASE_PHOTO_PATH, orig_key)
        preview_path = os.path.join(BASE_PHOTO_PATH, preview_key)

        try:
            os.makedirs(os.path.dirname(orig_path), exist_ok=True)
            logger.info(f"Директория для сохранения: {os.path.dirname(orig_path)}")
        except OSError as e:
            logger.error(f"Ошибка при создании директории: {e}")
            if e.errno == errno.EACCES:
                raise HTTPException(status_code=500, detail="Ошибка доступа к директории для записи.")
            raise HTTPException(status_code=500, detail="Ошибка при создании директории.")

        try:
            with open(orig_path, "wb") as f:
                f.write(orig_file_bytes)
            logger.info(f"Оригинальный файл сохранён: {orig_path}")
        except FileNotFoundError as e:
            logger.error(f"Файл не найден при записи оригинала: {e}")
            raise HTTPException(status_code=500, detail="Файл не найден при записи оригинала.")
        except PermissionError as e:
            logger.error(f"Нет прав для записи оригинала: {e}")
            raise HTTPException(status_code=500, detail="Нет прав для записи оригинала.")
        except OSError as e:
            logger.error(f"Ошибка при записи оригинала: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при записи оригинала.")

        try:
            with open(preview_path, "wb") as f:
                f.write(preview_file_bytes)
            logger.info(f"Превью сохранено: {preview_path}")
        except FileNotFoundError as e:
            logger.error(f"Файл не найден при записи превью: {e}")
            raise HTTPException(status_code=500, detail="Файл не найден при записи превью.")
        except PermissionError as e:
            logger.error(f"Нет прав для записи превью: {e}")
            raise HTTPException(status_code=500, detail="Нет прав для записи превью.")
        except OSError as e:
            logger.error(f"Ошибка при записи превью: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при записи превью.")

        return orig_key, preview_key

    @classmethod
    async def delete_photo_file(link: str, use_s3: bool = True):
        logger.info(f"Удаление файла: {link}")
        try:
            if use_s3:
                await asyncio.to_thread(cls().client.remove_object, cls().bucket_name, link)
                logger.info("Файл успешно удалён из S3")
            else:
                path = os.path.join(BASE_PHOTO_PATH, link)
                if os.path.exists(path):
                    os.remove(path)
                    logger.info("Файл успешно удалён локально")
                else:
                    logger.warning("Файл для удаления не найден локально")
        except Exception as e:
            logger.error(f"Ошибка при удалении файла: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при удалении файла")

    async def get_photo_file(self, date: str, identifier: UUID, filename: str) -> StreamingResponse:
        key = f"{date}/{identifier}/{filename}"
        logger.info(f"Получение файла: {key}")
        try:
            if self.use_s3:
                response = await asyncio.to_thread(self.client.get_object, self.bucket_name, key)
                media_type, _ = mimetypes.guess_type(filename)
                return StreamingResponse(response.stream(32 * 1024), media_type=media_type or "application/octet-stream")
            else:
                path = os.path.join(BASE_PHOTO_PATH, key)
                if not os.path.exists(path):
                    raise HTTPException(status_code=404, detail="Файл не найден локально")
                return StreamingResponse(open(path, "rb"), media_type=mimetypes.guess_type(filename)[0] or "application/octet-stream")
        except Exception as e:
            logger.error(f"Ошибка при получении файла: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при получении файла")
