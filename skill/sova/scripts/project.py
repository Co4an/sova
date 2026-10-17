#!/usr/bin/env python3
"""Local research state and structural checks. Standard library only, no network."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit


def save(path, value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.write-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as file:
            file.write(text)
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load(folder, name):
    return json.loads((folder/name).read_text(encoding='utf-8'))


@contextmanager
def lock(folder):
    path = folder/'.state.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Run is locked. If no process is using it, remove .state.lock and retry.')
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def strings(value):
    return isinstance(value,list) and bool(value) and all(isinstance(x,str) and x.strip() for x in value)


def plan_errors(folder):
    p = load(folder,'plan.json')
    if not isinstance(p,dict) or not strings(p.get('requirements')):
        return ['plan.json: requirements must be a nonempty list of strings']
    tasks = p.get('tasks')
    if not isinstance(tasks,list) or not tasks or len(tasks) > 12:
        return ['plan.json: use 1–12 research tasks']
    if any(not isinstance(t,dict) or not isinstance(t.get('id'),str) or
           not re.fullmatch(r'[a-z0-9-]+',t['id']) or not isinstance(t.get('question'),str)
           or not t['question'].strip() for t in tasks):
        return ['plan.json: each task needs a unique slug id and a question']
    if len({t['id'] for t in tasks}) != len(tasks):
        return ['plan.json: duplicate task IDs']
    return []


def source_errors(folder):
    sources = load(folder,'sources.json')
    if not isinstance(sources,list) or not sources:
        return ['sources.json: no evidence collected']
    seen, errors = set(), []
    for s in sources:
        if not isinstance(s,dict):
            errors.append('Source must be an object')
            continue
        sid = s.get('id','')
        if not isinstance(sid,str) or not re.fullmatch(r'S[1-9][0-9]*',sid) or sid in seen:
            errors.append('Source IDs must be unique S1, S2, ...')
        seen.add(str(sid))
        for field in ('title','accessed','locator','excerpt'):
            if not isinstance(s.get(field),str) or not s[field].strip():
                errors.append(f'{sid}: missing {field}')
        try:
            datetime.strptime(s.get('accessed',''),'%Y-%m-%d')
        except (ValueError,TypeError):
            errors.append(f'{sid}: accessed must be YYYY-MM-DD')
        url, local = s.get('url'), s.get('file')
        if not url and not local:
            errors.append(f'{sid}: supply url or file')
        if url:
            try:
                parts = urlsplit(url)
                if parts.scheme not in ('https','http') or not parts.hostname or parts.username or parts.password:
                    raise ValueError()
            except (TypeError,ValueError):
                errors.append(f'{sid}: invalid public source URL')
        if local:
            if not isinstance(local,str) or not (folder/local).is_file():
                errors.append(f'{sid}: local source file not found')
        if s.get('evidence') not in ('retrieved_text','abstract','search_excerpt','metadata_only'):
            errors.append(f'{sid}: invalid evidence type')
    return errors


def text_errors(folder, name):
    text = (folder/name).read_text(encoding='utf-8')
    if not text.strip():
        return [f'{name}: empty']
    allowed = {s['id'] for s in load(folder,'sources.json')}
    cited = set(re.findall(r'\[(S[0-9]+)\]',text))
    errors = [f'{name}: unknown citation [{sid}]' for sid in sorted(cited-allowed)]
    if not cited:
        errors.append(f'{name}: cite supplied evidence using [S1]')
    return errors


def review_errors(folder):
    r = load(folder,'review.json')
    if not isinstance(r,dict) or type(r.get('approved')) is not bool:
        return ['review.json: approved must be a boolean']
    if not isinstance(r.get('issues'),list) or any(not isinstance(i,str) or not i.strip() for i in r['issues']):
        return ['review.json: issues must be a list of nonempty strings']
    if r.get('reviewer') not in ('independent_agent','human','self_review'):
        return ['review.json: reviewer must identify independent_agent, human or self_review']
    rows = r.get('requirements')
    requirements = load(folder,'plan.json')['requirements']
    if not isinstance(rows,list) or any(not isinstance(row,dict) or
         not isinstance(row.get('requirement'),str) or type(row.get('met')) is not bool for row in rows):
        return ['review.json: requirements need requirement and boolean met']
    if sorted(row['requirement'] for row in rows) != sorted(requirements):
        return ['review.json: must assess every planned requirement exactly once']
    if r['approved'] and (r['issues'] or not all(row['met'] for row in rows)):
        return ['review.json: approval contradicts issues or unmet requirements']
    return []


def check(folder, stage):
    errors = plan_errors(folder)
    if errors or stage == 'plan':
        return errors
    errors += source_errors(folder)
    if errors or stage == 'research':
        return errors
    errors += text_errors(folder,'analysis.md')
    if stage == 'analysis':
        return errors
    errors += text_errors(folder,'report.md')
    if stage == 'draft':
        return errors
    return errors + review_errors(folder)


def init(folder, task):
    folder.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','research','final'):
        (folder/name).mkdir()
    for name, value in {'assignment.md':task + '\n','plan.json':{'requirements':[],'tasks':[]},
                        'sources.json':[],'analysis.md':'','report.md':'',
                        'review.json':{'approved':False,'issues':['Not reviewed'],
                                       'reviewer':'self_review','requirements':[]},
                        'state.json':{'version':1,'stage':'plan','revisions':0,
                                      'capabilities':{},'history':[]}}.items():
        save(folder/name,value)
    return load(folder,'state.json')


def advance(folder):
    with lock(folder):
        state = load(folder,'state.json')
        stage = state['stage']
        if stage in ('complete','needs_review'):
            raise ValueError('Run has finished; start a new run for a new revision cycle')
        errors = check(folder,stage)
        if errors:
            raise ValueError('\n'.join(errors))
        next_stage = {'plan':'research','research':'analysis','analysis':'draft','draft':'review'}
        if stage == 'review':
            review = load(folder,'review.json')
            # Preserve every review before a later pass overwrites it.
            save(folder/'research'/f"review-{state['revisions']}.json",review)
            if review['approved']:
                report = (folder/'report.md').read_text(encoding='utf-8')
                refs = '\n'.join(f"[{s['id']}] {s['title']} — {s.get('url') or s.get('file')} ({s['locator']}; {s['evidence']})"
                                 for s in load(folder,'sources.json'))
                label = 'Самопроверка' if review['reviewer'] == 'self_review' else 'Отдельный рецензент'
                save(folder/'final/report.md',report + '\n\n## Источники\n\n' + refs + '\n\nПроверка: ' + label + '\n')
                state['stage'] = 'complete'
            elif state['revisions'] >= 3:
                state['stage'] = 'needs_review'
            else:
                state['revisions'] += 1
                state['stage'] = 'analysis'
        else:
            state['stage'] = next_stage[stage]
        state['history'].append({'from':stage,'to':state['stage'],
                                 'at':datetime.now(timezone.utc).isoformat()})
        save(folder/'state.json',state)
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['init','status','check','advance'])
    parser.add_argument('folder',type=Path)
    parser.add_argument('--task')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            if not args.task or not args.task.strip():
                raise ValueError('--task is required')
            result = init(args.folder,args.task)
        elif args.command == 'advance':
            result = advance(args.folder)
        else:
            result = load(args.folder,'state.json')
            if args.command == 'check':
                errors = check(args.folder,result['stage'])
                if errors:
                    raise ValueError('\n'.join(errors))
                result = {'structural_checks':'passed','semantic_verification':'requires reviewer'}
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(str(exc),file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
