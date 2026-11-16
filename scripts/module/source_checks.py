#!/usr/bin/env python3
"""Inspect course source metadata, UTF-8 and literal local imports using Python.

No compilation, source execution, dependency installation or security certification.
Independently callable; returns valid modules, rejected inputs and warnings.
"""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / 'common')]
from course_metadata import module_errors
from module.source_inputs import discover_modules, source_paths
from common.submission_policy import outside_assets_violation, issue, OUTSIDE_ASSETS_LIMIT
from module.source_styles import custom_style, DEFAULT_STYLE
from skzip import MAX_FILE_BYTES, MAX_BYTES, MAX_FILES

CODE = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css'}
IMPORT = re.compile(r'''(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s*)['"](\.[^'"\r\n]+)['"]''')


def inspect_module(module, files):
    """Use the existing Python metadata contract; missing runtime code is not built."""
    doc = json.loads((module / 'outlines.json').read_text(encoding='utf-8-sig'))
    def exists(entry):
        return isinstance(entry, str) and entry in files
    errors = module_errors(doc, module.name, complete=True, exists=exists)
    if errors:
        raise ValueError('; '.join(errors))
    warnings = []
    if not doc.get('entry') and not (doc.get('ppt') or {}).get('entry'):
        warnings.append({'kind': 'outline-only', 'module': module.name,
                         'message': 'Source draft; server determines import eligibility'})
    missing = sum('assets/shuku-thumbnails/' + page['id'] + '.webp' not in files for page in doc['pages'])
    for name, path in files.items():
        if path.suffix.lower() not in CODE or path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding='utf-8-sig')
        except UnicodeError as error:
            invalid = ValueError('源码必须使用 UTF-8 编码，请转换该文件编码后重新打包。')
            invalid.path = str(path)
            invalid.code = 'SOURCE_ENCODING_INVALID'
            raise invalid from error
        if '\x00' in text:
            invalid = ValueError('源码包含 NUL 字节，请检查该文件是否为错误编码或伪装二进制。')
            invalid.path = str(path)
            invalid.code = 'SOURCE_NUL_BYTE'
            raise invalid
        for reference in IMPORT.findall(text):
            if any(p.casefold() == 'shared' for p in reference.replace('\\', '/').split('/')):
                continue
            target = (path.parent / reference).resolve()
            candidates = [target, *(Path(str(target) + ext) for ext in CODE | {'.json'}),
                          *(target / ('index' + ext) for ext in CODE)]
            if not target.is_relative_to(module) or not any(p.is_file() for p in candidates):
                warnings.append({'kind': 'unverified-import', 'module': module.name,
                                 'path': name, 'reference': reference})
    return {'id': doc['id'], 'title': doc.get('title') or '未命名标题',
            'pages': len(doc['pages']), 'files': len(files), 'missingThumbnails': missing}, warnings


def inspect_collection(directories):
    """Discover and check once; return the collected inventory for the next stage."""
    modules, shared = discover_modules(directories)
    files, accepted, rejected, warnings, identities = {}, [], [], [], set()
    serious, exclusions, passed = [], [], 0
    styles, default_styles = {}, set()
    for module in modules:
        try:
            excluded = []
            local = source_paths(module, [module], shared, excluded)
            for row in excluded:
                exclusions.append({'module': module.name, **row})
                warnings.append(issue('FILE_EXCLUDED', 'modules/'+module.name+'/'+row['path'],
                    '黑名单文件已从交付清单排除，原文件未删除。',
                    '该文件不会上传；如课件依赖它，必须先移除或替换该依赖。',
                    '检查课件是否依赖此文件；需要其数据时改为允许的静态资源。', reason=row['reason']))
            for name, path in local.items():
                if path.stat().st_size > MAX_FILE_BYTES:
                    serious.append(issue('FILE_TOO_LARGE', 'modules/'+module.name+'/'+name,
                        '文件超过 128 MiB 单文件上限。', '本地和服务器均不能接收此文件。',
                        '压缩或拆分资源后重新打包。', size=path.stat().st_size, limitBytes=MAX_FILE_BYTES))
                if outside_assets_violation(name, path.stat().st_size):
                    serious.append(issue('FILE_OUTSIDE_ASSETS', 'modules/'+module.name+'/'+name,
                        '非白名单文件超过 100 KiB，位于课件 assets/ 外。',
                        '服务器会拒绝导入。', '移至本课件 assets/，同步更新引用；不要改扩展名规避规则。',
                        size=path.stat().st_size, limitBytes=OUTSIDE_ASSETS_LIMIT, module=module.name))
                else:
                    passed += 1
            # Only literal references known to resolve to an excluded file block.
            excluded_names = {row['path'] for row in excluded}
            for name, path in local.items():
                if not excluded_names:
                    break
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                if path.suffix.lower() not in CODE | {'.json', '.html', '.svg'}:
                    continue
                text = path.read_text(encoding='utf-8-sig')
                for match in re.finditer(r'''[\"']([^\"'\r\n]+)[\"']''', text):
                    value = match.group(1).split('?', 1)[0].split('#', 1)[0]
                    candidate = (path.parent/value).resolve()
                    relative = candidate.relative_to(module).as_posix() if candidate.is_relative_to(module) else None
                    if value in excluded_names or relative in excluded_names:
                        serious.append(issue('EXCLUDED_FILE_REFERENCED', 'modules/'+module.name+'/'+name,
                            '源码引用了禁止打包的文件。', '文件已排除，继续交付会造成缺失资源或构建失败。',
                            '移除该依赖，或提取为允许的静态数据后更新引用。',
                            reference=value, line=text.count('\n', 0, match.start())+1, module=module.name))
            record, notes = inspect_module(module, local)
            dependencies, style, selected = custom_style(module)
            if style:
                styles[style['id']] = style
                for logical, physical in dependencies.items():
                    if logical in files and files[logical].read_bytes() != physical.read_bytes():
                        raise ValueError('同一风格 UUID 对应不同源码：'+style['id'])
                    files[logical] = physical
            outline = json.loads((module/'outlines.json').read_text(encoding='utf-8-sig'))
            if not outline.get('style_id'):
                default_styles.add(selected)
            if record['id'] in identities:
                raise ValueError('Duplicate module identity from multiple directories')
            identities.add(record['id'])
            accepted.append(record)
            passed += 1
            warnings.extend(notes)
            files.update({'modules/' + module.name + '/' + name: path for name, path in local.items()})
        except (ValueError, OSError, UnicodeError, TypeError, KeyError) as error:
            rejected.append({'directory': str(module), 'module':module.name,
                'path':getattr(error, 'path', None) or getattr(error, 'filename', None) or str(module/'outlines.json'),
                'code':getattr(error, 'code', 'MODULE_SOURCE_INVALID'),
                'line':getattr(error, 'lineno', None), 'column':getattr(error, 'colno', None),
                'reason': str(error)})
    if len(default_styles) > 1:
        serious.append(issue('STYLE_DEFAULT_CONFLICT', 'course-styles.json',
            '所选课件依赖不同的默认风格。', '合并后无法确定每门课使用哪个风格。',
            '在每门课 outlines.json 中显式填写 style_id 后重新打包。'))
    if len(files) >= MAX_FILES or sum(path.stat().st_size for path in files.values()) > MAX_BYTES:
        serious.append(issue('SOURCE_LIMIT_EXCEEDED', '', '文件数量或源码总量超过提交上限。',
            '不能进入图片加工和归档。', '减少所选课件范围，排除非交付文件，确保少于 10000 个文件、总量不超过 1 GiB。'))
    registry = {'schema':1, 'default_style':next(iter(default_styles), DEFAULT_STYLE), 'styles':list(styles.values())}
    return files, {'status': 'passed' if accepted and not rejected and not serious else 'failed', 'modules': accepted,
                   'moduleCount': len(accepted), 'rejectedModuleCount': len(rejected),
                   'rejectedModules': rejected, 'excludedShared': sorted(set(shared)),
                   'serious': serious, 'excludedFiles': exclusions, 'passedCheckCount': passed,
                   'styleRegistry': registry if styles else None,
                   'warningCount': len(warnings), 'warnings': warnings,
                   'coverage': 'Metadata, declared local entries, UTF-8 and literal import hints; no JS parsing, build or security review'}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='+', type=Path, help='Module, collection, project root, or several directories')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        _, report = inspect_collection(args.directories)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report['status'] == 'passed' else 1
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
