"""Export only ATLAS's maintained public development tracker with commit provenance."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'dashboard/progress.json'


def snapshot(repo):
    dirty = subprocess.check_output(
        ['git', '-C', str(repo), 'status', '--porcelain', '--', SOURCE], text=True).strip()
    if dirty:
        raise ValueError('Commit ATLAS progress changes before exporting a revision-labelled snapshot.')
    revision = subprocess.check_output(
        ['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    branch = subprocess.check_output(
        ['git', '-C', str(repo), 'branch', '--show-current'], text=True).strip()
    # Read exactly the committed tracker; never runtime databases, .env or broker files.
    content = subprocess.check_output(
        ['git', '-C', str(repo), 'show', f'{revision}:{SOURCE}'], text=True, encoding='utf-8')
    progress = json.loads(content)
    if not progress.get('milestones') or not progress.get('currentFeature'):
        raise ValueError('ATLAS tracker is missing milestones or currentFeature.')
    return dict(revision=revision, branch=branch, progress=progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    data = snapshot(args.repo)
    # Safe in external JavaScript and in HTML previews; all UI text is escaped too.
    payload = json.dumps(data, ensure_ascii=True, indent=2).replace('<', '\\u003c')
    (ROOT / 'atlas-progress.js').write_text(
        '"use strict";\nwindow.ATLAS_TRACKER = ' + payload + ';\n', encoding='utf-8')
    print(f'ATLAS snapshot {data["revision"][:7]}: {len(data["progress"]["milestones"])} milestones.')
