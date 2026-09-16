"""Create an explicit public-only Firebase bundle; never copy backend or local secrets."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ('index.html', 'forward.css', 'forward.js', 'dashboard.js', 'homepage-wip.js', 'portal-management.js', 'portal-auth.js')

def main():
    destination = ROOT/'public'
    destination.mkdir(exist_ok=True)
    # Refuse unexpected files rather than silently publishing or deleting them.
    unexpected = {p.name for p in destination.iterdir()}-set(ASSETS)
    if unexpected:
        raise SystemExit('Unexpected files in public/; inspect them before building: '+', '.join(sorted(unexpected)))
    for asset in ASSETS:
        shutil.copyfile(ROOT/asset, destination/asset)
    print('Built seven public assets. Backend, credentials and historical content excluded.')

if __name__ == '__main__':
    main()
