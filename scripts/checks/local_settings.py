"""Manage local dependency consent; no installs or services."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'common'))
from local_context import install_policy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    policy = sub.add_parser('policy', help='Read/save the user answer; unknown resets only at user request')
    policy.add_argument('--decision', choices=['allowed', 'declined', 'unknown'])
    policy.add_argument('--request-id')
    args = parser.parse_args(argv)
    try:
        result = install_policy(decision=args.decision, request_id=args.request_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
