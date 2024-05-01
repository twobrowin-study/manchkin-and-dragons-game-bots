import io
from pyzbar.pyzbar import decode
from PIL import Image

from telegram import PhotoSize

from loguru import logger

async def qr_convert(photo: PhotoSize) -> str|None:
    try:
        file = await photo.get_file()
        in_memory = io.BytesIO()
        await file.download_to_memory(in_memory)
        in_memory.seek(0)

        qr_decoded   = decode(Image.open(in_memory))
        qr_data: str = qr_decoded[0].data.decode("utf-8")
        return qr_data
    except Exception as e:
        logger.error(f"Got an error while processing qr code")
        return None