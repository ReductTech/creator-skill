"""Retain explicitly selected custom style dependencies; platform Shared is omitted."""
import json
from pathlib import Path

from common.submission_policy import outside_assets_violation, issue
from module.source_inputs import source_paths, linked

DEFAULT_STYLE = '76018445-20ab-4dd9-9543-385d177eb159'


def custom_style(module, *, warnings=None, exclusions=None):
    outline = json.loads((module/'outlines.json').read_text(encoding='utf-8-sig'))
    catalog_path = next((root/'course-styles.json' for root in (module.parent, module.parent.parent)
                         if (root/'course-styles.json').is_file()), None)
    catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig')) if catalog_path else {}
    selected = outline.get('style_id') or catalog.get('default_style', DEFAULT_STYLE)
    if selected == DEFAULT_STYLE:
        return {}, None, selected
    entry = next((s for s in catalog.get('styles', []) if s.get('id') == selected), None)
    if not entry or not catalog_path:
        raise ValueError('自定义风格未登记，请补齐 course-styles.json 和实际风格文件：'+str(selected))
    root = catalog_path.parent.resolve()
    relative = entry.get('path')
    if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('自定义风格路径必须在工程内')
    directory = root/relative
    if linked(directory) or not directory.resolve().is_relative_to(root):
        raise ValueError('自定义风格不得使用链接或越界路径')
    excluded = []
    local = source_paths(directory, [directory], excluded_files=excluded, preserve_shared=True)
    for row in excluded:
        logical = 'styles/'+selected+'/'+row['path']
        if exclusions is not None:
            exclusions.append({'module': module.name, 'style': selected, **row, 'path': logical})
        if warnings is not None:
            warnings.append(issue('FILE_EXCLUDED', logical,
                '黑名单文件已从自定义风格交付清单排除，原文件未删除。',
                '此类型不允许入包；继续打包，如风格依赖它，后续构建或运行可能失败。',
                '检查风格是否依赖此文件，移除或替换该依赖。', reason=row['reason']))
    if 'style.json' not in local:
        raise ValueError('自定义风格缺少 style.json')
    for name, file in local.items():
        if outside_assets_violation(name, file.stat().st_size):
            raise ValueError('自定义风格非白名单文件超过 100 KiB，请移入其 assets/：'+name)
    # Stable transport namespace; runtime imports resolve through the registry.
    prefix = 'styles/'+selected
    return {prefix+'/'+name:file for name,file in local.items()}, {'id':selected, 'path':prefix}, selected
