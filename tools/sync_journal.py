"""Publish documentation-only tracker data; never read runtime/account files."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def clean(value):
    value = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', value)
    return value.replace('**', '').replace('`', '').strip()

def table(document, heading):
    section = document.split('## ' + heading + '\n', 1)[1].split('\n## ', 1)[0]
    rows = [line for line in section.splitlines() if line.startswith('|')]
    return [[clean(cell) for cell in line.strip('|').split('|')] for line in rows[2:]]

def snapshot(repo):
    dirty = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain', '--', 'docs/development-tracker.md'], text=True).strip()
    if dirty:
        raise ValueError('Commit tracker changes before exporting a revision-labelled snapshot.')
    doc = (repo / 'docs/development-tracker.md').read_text(encoding='utf-8')
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    branch = subprocess.check_output(['git', '-C', str(repo), 'branch', '--show-current'], text=True).strip()
    milestones = []
    for key, title, status, evidence in table(doc, 'Milestone board'):
        state = 'validated' if status == 'Validated' else 'progress' if status == 'In progress' else 'planned'
        milestones.append(dict(id=key, title=title, status=status, state=state, evidence=evidence))
    return dict(revision=revision, branch=branch,
        updated=clean(re.search(r'Updated: \*\*(.+?)\*\*', doc).group(1)),
        checkpoint=clean(re.search(r'\*\*Current checkpoint:\*\* (.+)', doc).group(1)),
        next=clean(re.search(r'\*\*Next checkpoint:\*\* (.+)', doc).group(1)),
        milestones=milestones,
        tasks=[dict(title=a, status=b, evidence=c) for a,b,c in table(doc, 'Current work queue')],
        log=[dict(date=a, title=b, evidence=c) for a,b,c in table(doc, 'Validation log')])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    data = snapshot(args.repo)
    output = ROOT / 'nexy-journal.js'
    output.write_text('"use strict";\nwindow.NEXY_JOURNAL = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';\n', encoding='utf-8')
    print(f'Journal snapshot {data["revision"][:7]}: {len(data["milestones"])} milestones, {len(data["log"])} evidence entries.')
