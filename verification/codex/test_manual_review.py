import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import manual_review as review


class IsolationTests(unittest.TestCase):
    def test_task_does_not_include_next_user_task(self):
        steps = [{'type': 'USER_INPUT', 'step_index': 0}, {'type': 'GENERIC', 'step_index': 1},
                 {'type': 'USER_INPUT', 'step_index': 2}, {'type': 'PLANNER_RESPONSE', 'step_index': 3}]
        self.assertEqual(review.task_slice(steps, 0), steps[:2])

    def test_non_user_step_rejected(self):
        with self.assertRaises(ValueError):
            review.task_slice([{'type': 'GENERIC', 'step_index': 1}], 1)

    def test_ambiguous_task_rejected(self):
        with self.assertRaises(ValueError):
            review.task_slice([{'type': 'USER_INPUT', 'step_index': 0}] * 2, 0)

    def test_exact_workspace_and_alias_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / 'project'; project.mkdir()
            alias = root / 'alias'; alias.symlink_to(project)
            db = root / 'db.sqlite'
            with sqlite3.connect(db) as conn:
                conn.execute('create table conversation_summaries(conversation_id,title,last_modified_time,workspace_uris,not_fully_idle)')
                for name, path in [('right', alias), ('wrong', root / 'project-other')]:
                    conn.execute('insert into conversation_summaries values(?,?,?,?,?)', (name, '', '', json.dumps([path.as_uri()]), 0))
                conn.execute('insert into conversation_summaries values(?,?,?,?,?)', ('empty', '', '', '', 0))
            self.assertEqual([r['conversation_id'] for r in review.sessions(db, project)], ['right'])

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project = root / 'project'; project.mkdir()
            outside = root / 'outside'; outside.write_text('outside')
            (project / 'escape').symlink_to(outside)
            with self.assertRaises(ValueError): review.selected_files(project, ['escape'])

    def test_credentials_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / '.env').write_text('secret')
            with self.assertRaises(ValueError): review.selected_files(root, ['.env'])

    def test_incomplete_transcript_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = '04cbbce9-2f17-4d5b-ac36-9b5512741ca7'
            logs = Path(tmp) / session / '.system_generated/logs'; logs.mkdir(parents=True)
            (logs / 'transcript.jsonl').write_text('{"type":"USER_INPUT"}')
            with self.assertRaises(ValueError): review.read_steps(tmp, session)

    def test_snapshot_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'code.py').write_text('x = 1\n')
            files = review.selected_files(root, ['code.py'])
            self.assertEqual(files[0][0], 'code.py')
            self.assertEqual(review.digest(files[0][1]), review.digest(b'x = 1\n'))

    def test_runner_writes_guideline_and_rejects_wrong_task(self):
        # Mocked Codex subprocess: checks handoff artifacts, not model accuracy.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); out = base / 'reviews/bundle'; out.mkdir(parents=True)
            (out / 'evidence.json').write_text(json.dumps({'task_id': 'session:0', 'workspace': '/project', 'files': []}))
            (out / 'prompt.txt').write_text('Review')
            def fake_run(command, **kwargs):
                target = Path(command[command.index('-o') + 1])
                target.write_text(json.dumps({'task_id': 'session:0', 'verdict': 'inconclusive', 'report': 'Missing evidence', 'agy_guideline': 'Supply version evidence'}))
                return SimpleNamespace(returncode=0)
            args = SimpleNamespace(bundle=str(out), codex='codex', timeout=10)
            with patch.object(review, 'BASE', base), patch.object(review.subprocess, 'run', fake_run):
                review.run(args)
                self.assertIn('session:0', (out / 'agy-guideline.md').read_text())
                with self.assertRaises(ValueError): review.run(args)

    def test_runner_failure_has_no_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); out = base / 'reviews/bundle'; out.mkdir(parents=True)
            (out / 'evidence.json').write_text(json.dumps({'task_id': 'session:0', 'files': []}))
            (out / 'prompt.txt').write_text('Review')
            args = SimpleNamespace(bundle=str(out), codex='codex', timeout=10)
            with patch.object(review, 'BASE', base), patch.object(review.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
                with self.assertRaises(ValueError): review.run(args)
            self.assertFalse((out / 'report.md').exists())


if __name__ == '__main__': unittest.main()
