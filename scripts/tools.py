#!/usr/bin/env python3
"""Discover and run existing authoring tools: list, describe <id>, or <id> --help."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "common"))
from _common import SCRIPTS, get_target_root, report_error
SKILL = SCRIPTS.parent


def catalog():
    document=json.loads((SCRIPTS/'catalog.json').read_text(encoding='utf-8'))
    ids=set()
    for tool in document['tools']:
        target=(SKILL/tool['path']).resolve()
        if tool['id'] in ids or not target.is_relative_to(SKILL.resolve()) or not target.is_file(): raise ValueError(f"Invalid tool catalog entry: {tool['id']}")
        ids.add(tool['id'])
    return document['tools']


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    project = None
    bound_module = None
    if argv[:1] == ['--project']:
        if len(argv) < 3:
            print('Usage: tools.py --project <directory> [--module <id>] <tool-id> ...', file=sys.stderr)
            return 2
        project, argv = str(Path(argv[1]).resolve()), argv[2:]
        if argv[:1] == ['--module']:
            if len(argv) < 3:
                return 2
            bound_module, argv = argv[1], argv[2:]
    try:tools=catalog()
    except (ValueError,OSError) as exc:print(f'Tool catalog error: {exc}',file=sys.stderr);return 2
    if not argv or argv[0] in {'list','--help','-h','--json'}:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--json',action='store_true')
        parser.add_argument('--category',choices=sorted({tool['category'] for tool in tools}))
        args=parser.parse_args(argv[1:] if argv and argv[0]=='list' else argv)
        selected=[tool for tool in tools if not args.category or tool['category']==args.category]
        if args.json:print(json.dumps(selected,ensure_ascii=False,indent=2))
        else:
            print(f'Run: python "{Path(__file__).resolve()}" --project <directory> [--module <id>] <tool-id> ...')
            for tool in selected:print(f"{tool['id']:<32} {tool['description']} [{tool['category']}]")
        return 0
    describe=argv[0]=='describe'
    if describe:
        if len(argv)!=2:print('Usage: tools.py describe <tool-id>',file=sys.stderr);return 2
        key=argv[1]
    else:key=argv[0]
    tool=next((tool for tool in tools if tool['id']==key),None)
    if tool is None:print(f'Unknown tool: {key}; use list.',file=sys.stderr);return 2
    if describe:print(json.dumps({**tool,'help':f'python "{Path(__file__).resolve()}" {key} --help'},ensure_ascii=False,indent=2));return 0
    executable=sys.executable if tool['runtime']=='python' else shutil.which('node')
    if not executable:print('Node.js is unavailable; run environment.doctor.',file=sys.stderr);return 2
    command=[executable,str(SKILL/tool['path']),*tool.get('arguments',[]),*argv[1:]]
    try:
        environment = os.environ.copy()
        if project:
            environment['CREATOR_SKILL_PROJECT_ROOT'] = str(get_target_root(project))
        help_only = any(arg in {'--help', '-h'} for arg in argv[1:])
        explicit_paths = key in {'check.source-editing', 'course.pack', 'course.discover', 'course.inspect', 'course.images', 'course.videos', 'course.audio'}
        independent = {'check.skill', 'scratchpad.clean', 'environment.doctor', 'dependencies.policy', 'dependencies.install'}
        if project:
            root = Path(project)
        elif explicit_paths:
            root = Path.cwd()
        elif key in independent or help_only:
            root = SKILL
        else:
            root = get_target_root()
        if project and not help_only:
            bound_root = root
            scope_root = bound_root
            if bound_module:
                from _common import resolve_module
                scope_root = resolve_module(bound_module,bound_root)[0]
                if key=='module.identity' and '--check' not in argv:
                    raise ValueError('module.identity writes globally; use --check or an explicitly unbound project context')
                if key=='module.init':
                    raise ValueError('Create a new module from a project context, not a context bound to an existing course')
            if key in {'module.edit-ids','scratchpad.clean','assets.compress','course.videos','course.audio'}:
                if len(argv)<2 or argv[1].startswith('--'):
                    raise ValueError('Provide an explicit path within this window context')
                candidate=Path(argv[1])
                candidate=(candidate if candidate.is_absolute() else bound_root/candidate).resolve()
                if not candidate.is_relative_to(scope_root):
                    raise ValueError('Requested path leaves this window course/project scope')
                command[len(tool.get('arguments',[]))+2]=str(candidate)
                for option in ('--output','--report','--backup-dir'):
                    if option in argv:
                        value=Path(argv[argv.index(option)+1])
                        value=(value if value.is_absolute() else bound_root/value).resolve()
                        if not value.is_relative_to(scope_root):
                            raise ValueError('Output path leaves this window course/project scope')
            if key == 'check.source-editing':
                declared = next((arg.partition('=')[2] for arg in argv[1:] if arg.startswith('--project=')), None)
                if '--project' in argv[1:]:
                    index = argv.index('--project') + 1
                    if index >= len(argv):
                        raise ValueError('--project requires a directory')
                    declared = argv[index]
                if declared is None:
                    command.extend(['--project', str(root)])
                elif (root / declared).resolve() != root:
                    raise ValueError('Target overrides must match the selected project')
            if key == 'course.pack' and bound_module:
                environment['CREATOR_SKILL_PACK_MODULE'] = bound_module
            module_tools = {'check.module', 'check.outlines', 'check.course', 'check.styles', 'check.asset-imports', 'check.source-editing',
                            'capture.slides', 'capture.thumbnails', 'capture.inspect', 'assets.rewrite', 'analyze.pages', 'assets.upload'}
            if bound_module and key in module_tools:
                from _common import resolve_module
                bound = resolve_module(bound_module, bound_root)[0]
                selected = next((a.split('=',1)[1] for a in argv[1:] if a.startswith('--module=')),None)
                if '--module' in argv:
                    selected = argv[argv.index('--module')+1]
                if selected:
                    if resolve_module(selected, bound_root)[0] != bound:
                        raise ValueError('Requested module conflicts with this window context')
                else:
                    command.extend(['--module', bound_module])
        if key not in independent and not explicit_paths and not help_only:
            for index, argument in enumerate(argv[1:], 1):
                option, separator, value = argument.partition('=')
                if option in {'--repository', '--root'}:
                    value = value if separator else argv[index+1] if index+1 < len(argv) else ''
                    if not value or Path(value).resolve() != root:
                        raise ValueError('Target overrides must match the selected project')
        return subprocess.run(command,cwd=root,env=environment,check=False).returncode
    except ValueError as exc:return report_error(exc)
    except KeyboardInterrupt:return 130
    except OSError as exc:print(f'Could not run {key}: {exc}',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
