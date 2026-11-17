"""Plan literal media references with Python AST bindings; never execute course code.

Dynamic expressions are reported, not evaluated. Changes only affect staged files.
"""
import json
import posixpath
import re
from pathlib import PurePosixPath

CODE = {'.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx'}
DATA = {'.json', '.gltf'}
HELPERS = {'moduleAssetUrl', 'moduleJson'}


def parser_for(suffix):
    try:
        from tree_sitter import Language, Parser
        if suffix in {'.ts', '.tsx'}:
            import tree_sitter_typescript as grammar
            language = grammar.language_tsx() if suffix == '.tsx' else grammar.language_typescript()
        else:
            import tree_sitter_javascript as grammar
            language = grammar.language()
        return Parser(Language(language))
    except ImportError as error:
        raise RuntimeError('引用迁移需要 Python 包：pip install -r <Skill>/scripts/requirements-pack.txt；无需 Node。') from error


def rewrite_references(files, changes, directory):
    """Return staged inventory and actionable records, preserving original author files."""
    result, records, issues = dict(files), [], []
    if not changes:
        return result, {'changedFiles': 0, 'replacements': 0, 'issues': [], 'records': []}

    def problem(name, line, code, message, **details):
        issues.append({'code': code, 'path': name, 'line': line, 'message': message,
                       'repair': '在作者源码中使用原工程实际存在的完整输入路径或固定路径列表，再运行 course.pack；副本会自动迁移到成品路径。', **details})

    def replacement(name, value, line, *, helper=False):
        if not isinstance(value, str) or len(value) > 2048 or re.match(r'^(?:[\w+.-]+:|//|#)', value):
            return None
        clean = re.split(r'[?#]', value, maxsplit=1)[0]
        tail = value[len(clean):]
        parts = name.split('/')
        scope = '/'.join(parts[:2])
        candidates = [(posixpath.normpath(posixpath.join(posixpath.dirname(name), clean)), 'relative'),
                      (posixpath.normpath(scope+'/assets/'+clean), 'asset'),
                      (posixpath.normpath(scope+'/'+clean), 'scope')]
        matches = [(old, mode) for old, mode in candidates if old in changes]
        targets = {changes[old] for old, _ in matches}
        if len(targets) > 1:
            problem(name, line, 'REFERENCE_AMBIGUOUS', '同一字面量可对应多个转换目标。', source=value,
                    targets=sorted(targets), blocking=True)
            return None
        if not targets:
            return None
        old, mode = matches[0]
        target = changes[old]
        if mode == 'relative':
            new = posixpath.relpath(target, posixpath.dirname(name))
            if value.startswith('./') and not new.startswith('.'):
                new = './'+new
        elif mode == 'asset':
            new = posixpath.relpath(target, scope+'/assets')
        else:
            new = posixpath.relpath(target, scope)
        records.append({'path': name, 'line': line, 'source': value, 'target': new+tail})
        return new+tail

    for name, path in sorted(files.items()):
        scope = '/'.join(name.split('/')[:2])+'/'
        local_changes = {old: new for old, new in changes.items() if old.startswith(scope)}
        if not local_changes:
            continue
        suffix = PurePosixPath(name).suffix.lower()
        if suffix not in CODE | DATA | {'.css', '.html', '.htm', '.md', '.svg', '.xml'}:
            continue
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')
        edits = []
        if suffix in CODE:
            tree = parser_for(suffix).parse(raw)
            if tree.root_node.has_error:
                problem(name, 1, 'REFERENCE_SYNTAX_ERROR', '源码语法无法可靠解析，未迁移此文件。', blocking=True)
                continue
            helpers = set(HELPERS)
            def aliases(node):
                if node.type == 'import_specifier':
                    imported = node.child_by_field_name('name')
                    alias = node.child_by_field_name('alias')
                    if imported and alias and raw[imported.start_byte:imported.end_byte].decode() in HELPERS:
                        helpers.add(raw[alias.start_byte:alias.end_byte].decode())
                for child in node.named_children: aliases(child)
            aliases(tree.root_node)

            def visit(node):
                line = node.start_point.row+1
                token = raw[node.start_byte:node.end_byte].decode('utf-8')
                if node.type in {'binary_expression', 'call_expression'} and any(
                        PurePosixPath(old).suffix in token for old in changes
                        if old.startswith('/'.join(name.split('/')[:2])+'/')):
                    # Only concatenations/computed expressions, not ordinary literal helper calls.
                    if node.type == 'binary_expression' or any(c.type == 'binary_expression' for c in node.named_children):
                        problem(name, line, 'REFERENCE_COMPUTED', '计算或拼接的路径可能仍引用转换前素材。', expression=token[:240], blocking=True)
                if node.type == 'call_expression':
                    function = node.child_by_field_name('function')
                    args = node.child_by_field_name('arguments')
                    fn = raw[function.start_byte:function.end_byte].decode() if function else ''
                    values = args.named_children if args else []
                    if fn in helpers and (len(values) != 1 or values[0].type not in {'string', 'template_string'}):
                        problem(name, line, 'REFERENCE_DYNAMIC', '资源调用使用动态表达式，无法证明转换后的实际路径。',
                                expression=token[:240], blocking=True)
                if node.type in {'string', 'template_string'}:
                    if node.type == 'template_string' and any(c.type == 'template_substitution' for c in node.named_children):
                        scope = '/'.join(name.split('/')[:2])+'/'
                        converted = [old for old in changes if old.startswith(scope)]
                        fragments = [raw[c.start_byte:c.end_byte].decode('utf-8') for c in node.named_children if c.type == 'string_fragment']
                        if any(PurePosixPath(old).suffix in ''.join(fragments) for old in converted):
                            problem(name, line, 'REFERENCE_TEMPLATE', '模板路径可能仍生成转换前的文件名。', expression=token[:240], blocking=True)
                        return
                    value = token[1:-1]
                    if '\\' in value:
                        # JSON escapes can be decoded safely; JS-specific escapes need an explicit review.
                        try:
                            value = json.loads(token) if token.startswith('"') else None
                        except ValueError:
                            value = None
                        if value is None:
                            if any(PurePosixPath(old).suffix in token for old in changes):
                                problem(name, line, 'REFERENCE_ESCAPED', '含 JS 转义的资源字符串未自动改写。', expression=token[:240], blocking=True)
                            return
                    parent = node.parent
                    if parent and parent.type == 'pair' and parent.child_by_field_name('key') == node:
                        if any(PurePosixPath(old).name in (value or '') for old in local_changes):
                            problem(name, line, 'REFERENCE_KEY', '对象键包含转换前素材名，需核对它是稳定标识还是资源路径。',
                                    expression=token[:240], blocking=True)
                        return
                    new = replacement(name, value, line)
                    if new is not None:
                        if token[0] == '"': encoded = json.dumps(new, ensure_ascii=False)
                        else: encoded = token[0]+new.replace('\\', '\\\\').replace(token[0], '\\'+token[0])+token[0]
                        edits.append((node.start_byte, node.end_byte, encoded.encode('utf-8')))
                    elif isinstance(value, str) and any(char in value for char in '*?[') and any(PurePosixPath(old).suffix in value for old in local_changes):
                        problem(name, line, 'REFERENCE_GLOB', '通配符可能仍匹配转换前扩展名，需核对整个素材组。', expression=token[:240], blocking=True)
                    elif isinstance(value, str) and not re.match(r'^(?:[\w+.-]+:|//|#)', value) and any(PurePosixPath(old).name in value for old in local_changes):
                        problem(name, line, 'REFERENCE_EMBEDDED', '字符串中仍含转换前素材名，可能是 srcset、内嵌样式或未覆盖引用。',
                                expression=token[:240], blocking=True)
                    return
                for child in node.named_children:
                    visit(child)

            visit(tree.root_node)
            for start, end, value in sorted(edits, reverse=True):
                raw = raw[:start]+value+raw[end:]
        else:
            # JSON values, CSS URLs/imports, XML/HTML attributes and Markdown links.
            if suffix in DATA:
                json.loads(text)  # Validate before planning; keep original formatting.
                pattern = re.compile(r'"(?:[^"\\]|\\.)*"')
            elif suffix == '.css':
                pattern = re.compile(r'/\*.*?\*/|url\(\s*(?:"[^"\n]*"|\x27[^\x27\n]*\x27|[^)\n]*)\s*\)|@import\s+["\x27][^"\x27\n]+["\x27]', re.S)
            else:
                pattern = re.compile(r'<!--.*?-->|(?:src|href|poster|xlink:href)\s*=\s*["\x27][^"\x27\n]*["\x27]|!?\[[^\]\n]*\]\([^\s)]+\)', re.S)
            def update(match):
                token = match.group()
                if token.startswith(('/*', '<!--')):
                    return token
                if suffix in DATA:
                    if re.match(r'\s*:', text[match.end():]): return token
                    value = json.loads(token)
                    start, end = 0, len(token)
                elif token.startswith('url('):
                    inner = token[4:-1]
                    value = inner.strip().strip('"\x27')
                    start = token.index(value) if value else 0
                    end = start+len(value)
                elif '](' in token:
                    start, end = token.index('](')+2, len(token)-1
                    value = token[start:end]
                else:
                    quoted = re.search(r'["\x27](.*)["\x27]', token)
                    value = quoted[1]
                    start, end = quoted.span(1)
                line = text.count('\n', 0, match.start())+1
                new = replacement(name, value, line)
                if new is None: return token
                return json.dumps(new, ensure_ascii=False) if suffix in DATA else token[:start]+new+token[end:]
            after = pattern.sub(update, text)
            raw = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+after.encode('utf-8')
        if raw != path.read_bytes():
            target = directory/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            result[name] = target
        # Detect remaining references even when another reference in the file was migrated.
        if suffix not in CODE:
            remaining = raw.decode('utf-8-sig')
            remaining = re.sub(r'/\*.*?\*/|<!--.*?-->', '', remaining, flags=re.S)
            if any(PurePosixPath(old).name in remaining for old in local_changes):
                problem(name, 1, 'REFERENCE_REVIEW', '文件仍含转换前文件名，请确认是说明还是未覆盖的引用。', blocking=True)
    return result, {'changedFiles': sum(result[n] != files[n] for n in result),
                    'replacements': len(records), 'issues': issues, 'records': records,
                    'runtimeVerified': False,
                    'coverage': 'Literal AST/data/CSS/attribute references only; no arbitrary program evaluation, external data or real playback validation.'}
