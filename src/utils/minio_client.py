import asyncio
from io import BytesIO
from minio import Minio, S3Error
from loguru import logger
import filetype

from PIL import Image

class MinIOClient:
    """
    Обёртка для удобного асинхронного взаимодействия с MINIO
    """

    def __init__(self, access_key: str, secret_key: str, secure: bool, host: str) -> None:
        self.host = host
        self.base_url = f"{'https' if secure else 'http'}://{self.host}"
        self._client = Minio(self.host,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self._semaphore = asyncio.Semaphore(50)

    async def _put_object(self, bucket: str, filename: str, bio: BytesIO, content_type: str) -> None:
        """
        Внутренняя функция для асинхроанного помещения файла в заданный бакет
        """
        def _put_object_sync():
            bio.seek(0)
            self._client.put_object(
                bucket_name=bucket,
                object_name=filename,
                data=bio,
                length=bio.getbuffer().nbytes,
                content_type=content_type
            )
        await asyncio.get_event_loop().run_in_executor(None, _put_object_sync)

    async def upload(self, bucket: str, filename: str, bio: BytesIO, content_type: str) -> None:
        """
        Асинхронное помещение файла в бакет
        """
        async with self._semaphore:
            logger.info(f"Uploading {filename} to MinIO into bukcket {bucket}")
            await self._put_object(bucket, filename, bio, content_type)
        logger.success(f"Done uploading {filename} to MinIO into bukcket {bucket}")
    
    async def upload_with_thumbnail_and_return_filename(self, bucket: str, filename_wo_extension: str, bio: BytesIO) -> str:
        """
        Асинхронное помещение файла в бакет

        Если файл является изображением - вычисляется также уменьшенная версия и помещается рядом

        Возвращается имя файла или уменьшенной версии для сохранения в БД 
        """
        bio.seek(0)
        try:
            guessed_file = filetype.guess(bio)
            content_type = guessed_file.mime if guessed_file else 'application/octet-stream'
            extension    = guessed_file.extension if guessed_file else 'bin'
        except TypeError:
            content_type = 'application/octet-stream'
            extension    = 'bin'

        filename = f"{filename_wo_extension}.{extension}"
        await self.upload(bucket, filename, bio, content_type)

        if not content_type.startswith('image'):
            return filename
        
        image_format = content_type.removeprefix('image/').upper()
        
        bio.seek(0)
        with Image.open(bio, formats=[image_format]) as image:
            image.thumbnail((256, 256))

            thumbnail_bio = BytesIO()
            image.save(thumbnail_bio, format=image_format)
            
            thumbnail_filename = f"{filename_wo_extension}_thumbnail.{extension}"
            await self.upload(bucket, thumbnail_filename, thumbnail_bio, content_type)

            return thumbnail_filename

    async def download(self, bucket: str, filename: str) -> tuple[BytesIO | None, str]:
        """
        Асинхронная загрузка файла из бакета
        """
        logger.info(f"Downloading {filename} from MinIO bucket {bucket}")

        def _get_object():
            return self._client.get_object(bucket, filename)

        try:
            response = await asyncio.get_event_loop().run_in_executor(None, _get_object)
            logger.success(f"Done downloading {filename} from MinIO {bucket}")
            file_bytes   = BytesIO(response.read())
            content_type = response.getheader('content-type')
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.info(f"File {filename} not found in MinIO {bucket}")
                file_bytes   = None
                content_type = 'application/octet-stream'
            else:
                raise e
        else:
            response.close()
            response.release_conn()

        return file_bytes, content_type
    
    async def create_bucket(self, bucket: str) -> None:
        """
        Асинхронное создание бакета с доступом ко всем файлам по прямым ссылкам без авторизации
        """
        logger.info(f"Creating MinIO bucket {bucket}")
        def _create_bucket():
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
        await asyncio.get_event_loop().run_in_executor(None, _create_bucket)
        logger.success(f"Created MinIO bucket {bucket} or updated policyes")
