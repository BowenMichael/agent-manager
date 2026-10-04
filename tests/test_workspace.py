import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_manager.utils.workspace import find_local_workspace, _is_matching_repo
from agent_manager.config import WORKSPACE_BASE


class TestWorkspaceResolver(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp(prefix="agy_test_workspace_")
        self.base_path = Path(self.test_root)

    def tearDown(self):
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root, ignore_errors=True)

    def _create_mock_repo(self, rel_path: str, remote_url: str) -> Path:
        repo_dir = self.base_path / rel_path
        git_dir = repo_dir / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        config_file = git_dir / "config"
        config_content = f"""[core]
\trepositoryformatversion = 0
\tfilemode = false
\tbare = false
\tlogallrefupdates = true
\tsymlinks = false
\tignorecase = true
[remote "origin"]
\turl = {remote_url}
\tfetch = +refs/heads/*:refs/remotes/origin/*
"""
        config_file.write_text(config_content, encoding="utf-8")
        return repo_dir

    def test_find_local_workspace_direct_match(self):
        # Create repo directly under base_path
        created = self._create_mock_repo("agent-manager", "https://github.com/BowenMichael/agent-manager.git")

        with patch("agent_manager.utils.workspace.WORKSPACE_BASE", self.base_path):
            with patch("agent_manager.utils.workspace.Path.cwd", return_value=self.base_path / "somewhere_else"):
                found = find_local_workspace("BowenMichael/agent-manager")
                self.assertIsNotNone(found)
                self.assertEqual(found.resolve(), created.resolve())

    def test_find_local_workspace_nested_match(self):
        # Create nested repo: e.g. base_path / "SubFolder" / "f1-frontend"
        created = self._create_mock_repo("F1 Subfolder/f1-frontend", "git@github.com:BowenMichael/f1-frontend.git")

        with patch("agent_manager.utils.workspace.WORKSPACE_BASE", self.base_path):
            with patch("agent_manager.utils.workspace.Path.cwd", return_value=self.base_path / "somewhere_else"):
                found = find_local_workspace("BowenMichael/f1-frontend")
                self.assertIsNotNone(found)
                self.assertEqual(found.resolve(), created.resolve())

    def test_find_local_workspace_different_repo_not_matched(self):
        # Create an unrelated repo
        self._create_mock_repo("unrelated-project", "https://github.com/OtherOrg/unrelated-project.git")

        with patch("agent_manager.utils.workspace.WORKSPACE_BASE", self.base_path):
            with patch("agent_manager.utils.workspace.Path.cwd", return_value=self.base_path / "somewhere_else"):
                found = find_local_workspace("BowenMichael/target-repo")
                self.assertIsNone(found)

    def test_find_local_workspace_empty_or_none(self):
        self.assertIsNone(find_local_workspace(""))
        self.assertIsNone(find_local_workspace(None))

    def test_is_matching_repo_helper(self):
        repo_dir = self._create_mock_repo("sample-repo", "https://github.com/BowenMichael/sample-repo.git")
        self.assertTrue(_is_matching_repo(repo_dir, "BowenMichael/sample-repo"))
        self.assertFalse(_is_matching_repo(repo_dir, "BowenMichael/other-repo"))


if __name__ == "__main__":
    unittest.main()
