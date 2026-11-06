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
            print(f'Run: python "{Path(__file__).resolve()}" <tool-id> --help')
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
        root = SKILL if key == 'check.skill' else get_target_root()
        if key != 'check.skill':
            for index, argument in enumerate(argv[1:], 1):
                option, separator, value = argument.partition('=')
                if option in {'--repository', '--root'}:
                    value = value if separator else argv[index+1] if index+1 < len(argv) else ''
                    if not value or Path(value).resolve() != root:
                        raise ValueError('Target overrides must match targetRoot in target-root.json')
        return subprocess.run(command,cwd=root,check=False).returncode
    except ValueError as exc:return report_error(exc)
    except KeyboardInterrupt:return 130
    except OSError as exc:print(f'Could not run {key}: {exc}',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
