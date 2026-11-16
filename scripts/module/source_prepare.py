"""Pillow-only image optimization; JS/CSS references stay unchanged for the server."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath

from common.submission_policy import issue


def prepare_images(files, directory):
    result, conversions, warnings, counts = dict(files), [], [], Counter()
    candidates = [(name, path) for name, path in files.items()
                  if name.startswith('modules/') and path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.avif'}
                  and '/assets/' in name and '/shuku-thumbnails/' not in name]
    if candidates:
        try:
            from PIL import Image, ImageOps
        except ImportError as error:
            raise ValueError('图片加工需要 Pillow；请安装 Python 包 Pillow 后重新打包，无需 Node。') from error
    for name, path in candidates:
        counts['inspected'] += 1
        original = path.read_bytes()
        try:
            with Image.open(BytesIO(original)) as source:
                if source.width * source.height > 40_000_000:
                    raise ValueError('图片解码像素超过 4000 万上限')
                source.load()
                expected = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP'}.get(path.suffix.lower())
                if expected is None:
                    raise ValueError('本地不转换该图片格式，保留原文件由服务器处理')
                if source.format != expected:
                    raise ValueError('扩展名与实际图片类型不匹配')
                if getattr(source, 'n_frames', 1) != 1 or source.mode not in {'RGB', 'RGBA', 'L', 'LA', 'P', 'CMYK'} or '/image-atlases/' in name:
                    raise ValueError('动画、高位深或坐标图集保留原样，由服务器处理')
                image = ImageOps.exif_transpose(source)
                scale = min(1, 1600/image.width, 900/image.height)
                if source.format == 'WEBP' and scale == 1:
                    counts['reused'] += 1
                    continue
                target = str(PurePosixPath(name).with_suffix('.webp'))
                if target != name and any(p.casefold() == target.casefold() for p in files):
                    raise ValueError('目标 WebP 路径已存在，不覆盖、不猜测对应关系')
                alpha = image.mode in {'RGBA', 'LA'} or 'transparency' in image.info
                image = image.convert('RGBA' if alpha else 'RGB')
                image = image.resize((max(1, round(image.width*scale)), max(1, round(image.height*scale))), Image.Resampling.LANCZOS)
                stream = BytesIO()
                image.save(stream, format='WEBP', quality=80, method=6)
                raw = stream.getvalue()
                with Image.open(BytesIO(raw)) as checked:
                    checked.load()
                    if checked.format != 'WEBP' or checked.size != image.size:
                        raise ValueError('输出 WebP 复验失败')
                if len(raw) >= len(original) and scale == 1:
                    counts['retained'] += 1
                    continue
                output = directory / target
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(raw)
                result.pop(name)
                result[target] = output
                conversions.append({'source': name, 'target': target,
                    'source_sha256': sha256(original).hexdigest(), 'sha256': sha256(raw).hexdigest(),
                    'source_size': len(original), 'size': len(raw),
                    'width': image.width, 'height': image.height, 'quality': 80})
                counts['converted'] += 1
        except (OSError, ValueError, EOFError, Image.DecompressionBombError) as error:
            counts['retained'] += 1
            warnings.append(issue('IMAGE_RETAINED', name, str(error),
                '原文件仍会上传，服务器需要检查和处理，可能增加体积或因损坏失败。',
                '检查该图片；修复损坏文件或接受原样上传，由服务器处理。'))
    return result, {'status': 'warning' if warnings else 'passed', 'counts': dict(counts),
        'converted': counts['converted'], 'conversions': conversions, 'issues': warnings,
        'savedBytes': sum(row['source_size']-row['size'] for row in conversions)}
