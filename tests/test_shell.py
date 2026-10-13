import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_ui', ROOT / 'tools/build_ui.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class ShellTests(unittest.TestCase):
    def test_only_shell_assets_are_published(self):
        self.assertEqual(set(build.ASSETS), {'index.html', 'portal-shell.css', 'portal-shell.js', 'portal-auth.js', 'nexy-journal.js'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for asset in build.ASSETS:
                (root / asset).write_text(asset)
            (root / '.env').write_text('private')
            with patch.object(build, 'ROOT', root):
                build.main()
            self.assertEqual({p.name for p in (root / 'public').iterdir()}, set(build.ASSETS))

    def test_build_refuses_unexpected_public_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'public').mkdir()
            (root / 'public' / 'secret.env').write_text('private')
            with patch.object(build, 'ROOT', root), self.assertRaises(SystemExit):
                build.main()

    def test_broker_source_and_launch_tools_are_removed(self):
        self.assertFalse(list((ROOT / 'trading_backend').rglob('*.py')))
        self.assertFalse(list((ROOT / 'trading_backend').rglob('*.pyc')))
        self.assertEqual({p.name for p in (ROOT / 'tools').glob('*.py')}, {'build_ui.py', 'sync_journal.py'})
        self.assertFalse(list((ROOT / 'tools').glob('install-*-service.ps1')))
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('firebase-firestore', html)
        self.assertNotIn('page-', html)
        self.assertNotIn('firebase.firestore', (ROOT / 'portal-auth.js').read_text())

    def test_shell_cannot_issue_firestore_commands(self):
        rules = (ROOT / 'firestore.rules').read_text()
        self.assertIn('allow read, write: if false;', rules)
        self.assertNotIn('allow create', rules)


if __name__ == '__main__':
    unittest.main()
