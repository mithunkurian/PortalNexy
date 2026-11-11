"""The portal must export committed tracker data without runtime access."""
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_atlas', ROOT / 'tools/sync_atlas.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class AtlasTests(unittest.TestCase):
    def test_dirty_tracker_refused(self):
        with patch.object(sync.subprocess, 'check_output', return_value=' M dashboard/progress.json'):
            with self.assertRaisesRegex(ValueError, 'Commit ATLAS progress'):
                sync.snapshot(Path('not-read'))

    def test_only_committed_document_is_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            (repo / 'dashboard').mkdir()
            document = '{"milestones":[{"id":"M2"}],"currentFeature":"M2.1"}'
            (repo / 'dashboard/progress.json').write_text(document)
            (repo / '.env').write_text('secret-never-export')
            subprocess.run(['git', '-C', str(repo), 'add', 'dashboard/progress.json'], check=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'tracker'], check=True)
            result = sync.snapshot(repo)
            self.assertEqual(result['progress']['currentFeature'], 'M2.1')
            self.assertEqual(len(result['revision']), 40)
            self.assertNotIn('secret-never-export', str(result))
