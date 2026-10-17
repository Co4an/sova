#!/usr/bin/env python3
"""Install a project-local skill without dependencies or network access."""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys

SOURCE = Path(__file__).resolve().parent/'skill/sova'
PATHS = {'codex':['.agents'],'claude':['.claude'],'antigravity':['.agents'],
         'all':['.agents','.claude']}
PERSONAL_PATHS = {'codex':['.codex'],'claude':['.claude'],
                  'antigravity':['.gemini/config'],
                  'all':['.codex','.claude','.gemini/config']}


def digest(folder):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def install(target, app, personal=False):
    if not (SOURCE/'SKILL.md').is_file():
        raise ValueError('Skill package is incomplete')
    locations = PERSONAL_PATHS if personal else PATHS
    targets = [target/name/'skills/sova' for name in locations[app]]
    source_hash = digest(SOURCE)
    # Check all destinations before any mutation.
    for dst in targets:
        if dst.exists() and (not dst.is_dir() or digest(dst) != source_hash):
            raise ValueError(f'Existing skill differs: {dst}. Preserve or rename it before installation.')
    for dst in targets:
        if not dst.exists():
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copytree(SOURCE,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        print(dst)
    print('Ready. Open this project in your IDE; reload skills or start a new chat if needed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--target',type=Path,default=Path.cwd())
    scope.add_argument('--personal',action='store_true',help='Install for all local projects in selected apps')
    parser.add_argument('--app',choices=PATHS,default='all')
    args = parser.parse_args()
    try:
        install(Path.home() if args.personal else args.target.resolve(),args.app,personal=args.personal)
    except (OSError,ValueError) as exc:
        print(str(exc),file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
