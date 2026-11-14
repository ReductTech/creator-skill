"""Fixed publishing profiles: agents select a course/page, never pixel sizes."""
from PIL import Image, ImageOps

THUMBNAIL_SIZE = (1600, 900)
COVER_SIZE = THUMBNAIL_SIZE
THUMBNAIL_QUALITY = 20


def thumbnail_image(image):
    rgba = ImageOps.contain(ImageOps.exif_transpose(image).convert('RGBA'), THUMBNAIL_SIZE,
                           Image.Resampling.LANCZOS)
    background = Image.new('RGB', THUMBNAIL_SIZE, 'white')
    background.paste(rgba, ((THUMBNAIL_SIZE[0] - rgba.width) // 2,
                           (THUMBNAIL_SIZE[1] - rgba.height) // 2), rgba)
    return background


def _save(image, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_image(image).save(target, format='WEBP', quality=THUMBNAIL_QUALITY, method=6)


def save_thumbnail(image, target):
    _save(image, target)


def save_cover(image, target):
    _save(image, target)
