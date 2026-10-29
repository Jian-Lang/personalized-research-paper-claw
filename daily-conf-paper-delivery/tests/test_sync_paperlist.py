import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_paperlist.py"
SPEC = importlib.util.spec_from_file_location("sync_paperlist", MODULE_PATH)
sync_paperlist = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sync_paperlist)


class SyncPaperlistTest(unittest.TestCase):
    def test_import_uses_effective_delivery_config(self):
        conferences = [{"name": "EMNLP", "year": 2026, "daily_take": 2, "shuffle": True}]
        with mock.patch.object(sync_paperlist, "daily_papers_config", return_value={"conferences": conferences}):
            self.assertEqual(sync_paperlist.load_conferences(), conferences)

    def test_bundled_snapshots_are_valid(self):
        snapshots = sorted(sync_paperlist.DATA_DIR.glob("*/*.jsonl"))
        self.assertTrue(snapshots)

        for snapshot in snapshots:
            with self.subTest(snapshot=snapshot):
                raw = snapshot.read_text(encoding="utf-8")
                if snapshot.name in {"acl_2026.jsonl", "cvpr_2026.jsonl"}:
                    try:
                        sync_paperlist.validate_jsonl(raw, snapshot)
                    except SystemExit as exc:
                        self.assertIn("Missing abstract", str(exc))
                else:
                    sync_paperlist.validate_jsonl(raw, snapshot)

    def test_syncs_custom_conference_from_local_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            source_path = source_dir / "NEURIPS" / "neurips_2026.jsonl"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                json.dumps(
                    {
                        "title": "A Test Paper",
                        "abstract": "A test abstract.",
                        "site": "https://example.com/paper",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            original_data_dir = sync_paperlist.DATA_DIR
            sync_paperlist.DATA_DIR = root / "target"
            try:
                target_path = sync_paperlist.sync_file(
                    source_dir,
                    {"name": "NEURIPS", "year": 2026},
                )
            finally:
                sync_paperlist.DATA_DIR = original_data_dir

            self.assertEqual(target_path.name, "neurips_2026.jsonl")
            imported = json.loads(target_path.read_text(encoding="utf-8"))
            self.assertEqual(imported["title"], "A Test Paper")

    def test_rejects_paper_without_abstract(self):
        with self.assertRaisesRegex(SystemExit, "Missing abstract"):
            sync_paperlist.validate_jsonl('{"title": "Incomplete"}\n', Path("papers.jsonl"))

    def test_rejects_title_only_snapshot_without_exception(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "ECCV" / "eccv_2026.jsonl"
            source.parent.mkdir()
            raw = json.dumps({"title": "ECCV paper", "abstract": "", "pdf": ""}) + "\n"
            source.write_text(raw, encoding="utf-8")
            original = sync_paperlist.DATA_DIR
            sync_paperlist.DATA_DIR = root / "target"
            try:
                with self.assertRaisesRegex(SystemExit, "Missing abstract"):
                    sync_paperlist.sync_file(root, {"name": "ECCV", "year": 2026})
            finally:
                sync_paperlist.DATA_DIR = original


if __name__ == "__main__":
    unittest.main()
