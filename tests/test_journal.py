"""Protect the provenance and status semantics of the documentation export."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_journal', ROOT / 'tools/sync_journal.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

class JournalTests(unittest.TestCase):
    def test_table_keeps_partial_evidence_and_locked_status(self):
        text = '''## Milestone board
| ID | Title | Status | Evidence |
| --- | --- | --- | --- |
| M2B | Research | **In progress** | Quote validated; broader research pending |
| M4 | Execution | **Planned; locked** | Signed permits pending |

## Other section
| private | data |
'''
        rows = sync.table(text, 'Milestone board')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][2], 'In progress')
        self.assertIn('pending', rows[0][3])
        self.assertEqual(rows[1][2], 'Planned; locked')

    def test_dirty_tracker_cannot_claim_committed_provenance(self):
        with patch.object(sync.subprocess, 'check_output', return_value=' M docs/development-tracker.md'):
            with self.assertRaisesRegex(ValueError, 'Commit tracker changes'):
                sync.snapshot(Path('unread-repository'))

if __name__ == '__main__':
    unittest.main()
