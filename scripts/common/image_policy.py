"""Validate submitted images without changing bytes, names or references."""
from io import BytesIO
from pathlib import PurePosixPath
import re
from xml.etree import ElementTree

IMAGE_SUFFIXES = {'.webp', '.gif', '.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.avif', '.svg', '.ico', '.heic', '.heif', '.apng', '.jxl', '.jfif'}
def inspect_image(name, raw):
    suffix = PurePosixPath(name).suffix.lower()
    detected = ('WEBP' if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP' else
                'GIF' if raw.startswith((b'GIF87a', b'GIF89a')) else None)
    raster = raw.startswith((b'\x89PNG', b'\xff\xd8\xff', b'BM', b'II*\x00', b'MM\x00*')) or (b'ftyp' == raw[4:8] and raw[8:12] in {b'avif', b'avis', b'heic', b'heix', b'hevc', b'hevx', b'mif1', b'msf1'})
    # Inline SVG in TSX/HTML is source code, not a submitted image file.
    svg = bool(re.match(
        rb'(?:<\?xml\b.*?\?>\s*|<!--.*?-->\s*)*<(?:[A-Za-z_][\w.-]*:)?svg(?:\s|/?>)',
        raw[:4096].lstrip(b'\xef\xbb\xbf \r\n\t'), re.S))
    if suffix not in IMAGE_SUFFIXES and not detected and not raster and not svg:
        return None
    if suffix == '.svg':
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError as error:
            raise ValueError('SVG XML 损坏或格式不合法。') from error
        if root.tag not in {'svg', '{http://www.w3.org/2000/svg}svg'}:
            raise ValueError('SVG 必须以 SVG 元素为根节点。')
        return {'format': 'SVG'}
    if suffix != '.webp' or detected != 'WEBP':
        raise ValueError('图片仅允许真实 SVG 或 WebP，且扩展名必须匹配；SVG 原样保留、不转换，其他格式须转换并更新引用。')
    from PIL import Image
    with Image.open(BytesIO(raw)) as image:
        if image.format != detected or image.width * image.height > 40_000_000:
            raise ValueError('图片格式错误或像素超过 4000 万上限。')
        frames = 0
        while True:
            image.load()
            frames += 1
            if frames > 1000:
                raise ValueError('动画超过 1000 帧上限。')
            try:
                image.seek(image.tell() + 1)
            except EOFError:
                break
        return {'format':detected, 'width':image.width, 'height':image.height, 'frames':frames}
