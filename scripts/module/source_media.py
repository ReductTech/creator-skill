"""Prepare image/video/audio delivery bytes in a private staging directory.

Original files are never overwritten. The selected reference planner never executes course source.
"""
from collections import Counter
from pathlib import PurePosixPath
import shutil

from common.image_policy import IMAGE_SUFFIXES, inspect_image
from media import prepare_videos as video, prepare_audio as audio
from module.source_references import rewrite_references


def prepare_media(files, directory, *, ffmpeg='ffmpeg', ffprobe='ffprobe', reference_runner=None):
    result, conversions, issues = dict(files), [], []
    counts = Counter()
    images = {'status': 'passed', 'counts': {}, 'converted': 0, 'conversions': [], 'issues': []}
    reserved_names = {name.casefold() for name in files}

    def problem(name, code, error, **details):
        issues.append({'code': code, 'path': name, 'message': str(error), 'blocking': True,
                       'repair': '检查原始素材及依赖，按本项信息修复后重新运行 course.pack。', **details})

    def destination(name, target_name):
        if target_name != name and target_name.casefold() in reserved_names:
            raise ValueError('转换目标与现有文件冲突，未覆盖：'+target_name)
        reserved_names.add(target_name.casefold())
        target = directory/'media'/target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    for name, source in sorted(files.items()):
        suffix = source.suffix.lower()
        # .ts under source code is TypeScript, not an MPEG transport stream.
        is_video = suffix in video.EXTENSIONS and (suffix != '.ts' or 'assets' in PurePosixPath(name).parts)
        kind = 'image' if suffix in IMAGE_SUFFIXES else 'video' if is_video else 'audio' if suffix in audio.EXTENSIONS else None
        if kind is None:
            continue
        counts[kind+'Inspected'] += 1
        try:
            if kind == 'image' and suffix == '.svg':
                inspect_image(name, source.read_bytes())
                counts['preserved'] += 1
                continue
            target_name = name
            if kind == 'image':
                from PIL import Image, ImageOps
                from media.thumbnail_profiles import thumbnail_image
                with Image.open(source) as original:
                    expected = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.gif': 'GIF',
                                '.webp': 'WEBP', '.bmp': 'BMP', '.tif': 'TIFF', '.tiff': 'TIFF', '.avif': 'AVIF',
                                '.ico': 'ICO', '.apng': 'PNG', '.jfif': 'JPEG'}
                    if expected.get(suffix) != original.format:
                        raise ValueError('图片后缀和真实格式不匹配；请先修正文件名与引用。')
                    thumbnail = any(p in {'shuku-thumbnails', 'scenedeck-thumbnails', 'course-thumbnails', 'course-covers'} for p in PurePosixPath(name).parts)
                    atlas = 'image-atlases' in PurePosixPath(name).parts
                    width, height = ImageOps.exif_transpose(original).size
                    frame_count = getattr(original, 'n_frames', 1)
                    if width*height > 40_000_000 or frame_count > 1000:
                        raise ValueError('图片超过像素或帧数限制。')
                    scale = 1 if atlas else min(1, 1600/width, 900/height)
                    size = (max(1, round(width*scale)), max(1, round(height*scale)))
                    if suffix == '.webp' and scale == 1 and (not thumbnail or (width, height) == (1600, 900)):
                        inspect_image(name, source.read_bytes())
                        counts['preserved'] += 1
                        continue
                    if original.mode not in {'RGB', 'RGBA', 'P', 'L', 'LA', 'CMYK'}:
                        raise ValueError('高位深图片需作者确定色彩转换方式。')
                    target_name = str(PurePosixPath(name).with_suffix('.webp'))
                    target = destination(name, target_name)
                    frames, durations, pixels = [], [], 0
                    loop = original.info.get('loop', 0)
                    for index in range(frame_count):
                        original.seek(index)
                        frame = ImageOps.exif_transpose(original).convert('RGBA')
                        frame = thumbnail_image(frame) if thumbnail else frame.resize(size, Image.Resampling.LANCZOS)
                        pixels += frame.width*frame.height
                        if pixels > 80_000_000:
                            raise ValueError('动画累计解码像素超过 8000 万，请先缩短或拆分。')
                        frames.append(frame)
                        durations.append(original.info.get('duration', 100))
                    options = {'quality': 20 if thumbnail else 80, 'method': 6}
                    if len(frames) > 1:
                        options.update(save_all=True, append_images=frames[1:], duration=durations, loop=loop)
                    frames[0].save(target, format='WEBP', **options)
                    inspect_image(target_name, target.read_bytes())
                    with Image.open(target) as encoded:
                        if encoded.size != frames[0].size or encoded.n_frames != len(frames):
                            raise ValueError('转换后图片尺寸或动画帧数不一致。')
            else:
                encoder, prober = shutil.which(ffmpeg), shutil.which(ffprobe)
                if not encoder or not prober:
                    raise RuntimeError('音视频需要 FFmpeg 和 ffprobe；请安装或使用 --ffmpeg / --ffprobe 指定路径，无需 Node。')
                document = video.probe(prober, source)
                if kind == 'video':
                    target_name = name if suffix == '.mp4' else name+'.720p.mp4'
                    target = destination(name, target_name)
                    video.encode(encoder, prober, source, target, document, video.dimensions(video.video_stream(document)), 24)
                else:
                    target_name = name if suffix == '.m4a' else name+'.compressed.m4a'
                    target = destination(name, target_name)
                    channels, sample_rate = audio.settings(document)
                    audio.encode(encoder, prober, source, target, document, channels, sample_rate, 96)
                if sum(s.get('codec_type') == 'audio' for s in document['streams']) > 1:
                    issues.append({'code': 'MEDIA_FIRST_TRACK', 'path': name, 'message': '仅保留第一条音轨，请试听确认。', 'blocking': False})
            if not target.is_file() or not target.stat().st_size:
                raise ValueError('转换输出缺失或为空。')
            before, after = source.stat().st_size, target.stat().st_size
            conversions.append({'type': kind, 'source': name, 'target': target_name, 'beforeBytes': before, 'afterBytes': after})
            if after >= before:
                issues.append({'code': 'MEDIA_NOT_SMALLER', 'path': name, 'source': name, 'target': target_name,
                               'message': '格式统一后体积未减小，请核对质量与是否需要保留此素材。', 'blocking': False})
            result.pop(name)
            result[target_name] = target
            counts[kind+'Converted'] += 1
        except (ValueError, OSError, RuntimeError, KeyError, ImportError) as error:
            problem(name, 'MEDIA_PREPARE_FAILED', error)

    changes = {row['source']: row['target'] for row in conversions if row['source'] != row['target']}
    try:
        result, references = (reference_runner or rewrite_references)(result, changes, directory/'references')
        issues.extend(references['issues'])
    except (ValueError, OSError, RuntimeError) as error:
        references = {'changedFiles': 0, 'replacements': 0, 'records': [], 'issues': []}
        problem('', 'REFERENCE_PREPARE_FAILED', error)
    for name, source in result.items():
        try:
            inspect_image(name, source.read_bytes())
        except (ValueError, OSError, EOFError) as error:
            # Failed conversion already has a more useful per-file diagnostic.
            if not any(i['path'] == name and i.get('blocking') for i in issues):
                problem(name, 'IMAGE_INVALID', error)
    images.update(counts={'inspected': counts['imageInspected']}, converted=counts['imageConverted'])
    image_names = {name for name, path in files.items() if path.suffix.lower() in IMAGE_SUFFIXES}
    if any(i.get('blocking') and i['path'] in image_names for i in issues):
        images['status'] = 'failed'
    return result, {'status': 'failed' if any(i.get('blocking') for i in issues) else 'passed',
                    'counts': dict(counts), 'conversions': conversions, 'references': references,
                    'issues': issues, 'savedBytes': sum(r['beforeBytes']-r['afterBytes'] for r in conversions)}, images
