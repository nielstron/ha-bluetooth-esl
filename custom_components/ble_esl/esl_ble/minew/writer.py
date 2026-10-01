from ..base import WriteRefused
from .image import encode_image


def prepare(preset, image, address):
    return encode_image(image, preset)


async def write_session(*args, **kwargs):
    raise WriteRefused("Minew authentication and image writes are not yet verified")
