from __future__ import annotations

from pathlib import Path

import pytest

from harness.tools import ToolCall, execute
from harness.tools.fs import (
    CopyPath,
    DeletePath,
    EditFile,
    GlobFiles,
    GrepWorkspace,
    ListFiles,
    Mkdir,
    MovePath,
    PathStat,
    ReadFile,
    WorkspaceScope,
    WriteFile,
)


def _scope(tmp: Path) -> WorkspaceScope:
    return WorkspaceScope(root=tmp)


def test_workspace_scope_escape(tmp_path: Path) -> None:
    s = _scope(tmp_path)
    (tmp_path / "inside").mkdir()
    s.resolve("inside")
    with pytest.raises(ValueError, match="escapes"):
        s.resolve("..")


def test_read_file_full_and_lines(tmp_path: Path) -> None:
    p = tmp_path / "a.txt"
    p.write_text("line1\nline2\nline3\n", encoding="utf-8")
    s = _scope(tmp_path)
    r = ReadFile(s)
    assert r.run({"path": "a.txt"}) == "line1\nline2\nline3\n"
    assert r.run({"path": "a.txt", "line_start": 2, "line_end": 2}) == "line2\n"
    assert r.run({"path": "a.txt", "line_start": 2, "line_end": 3}) == "line2\nline3\n"
    assert r.run({"path": "a.txt", "offset": 6, "limit": 5}) == "line2"


def test_read_file_max_chars(tmp_path: Path) -> None:
    p = tmp_path / "b.txt"
    p.write_text("abcdefghij", encoding="utf-8")
    s = _scope(tmp_path)
    r = ReadFile(s)
    out = r.run({"path": "b.txt", "max_chars": 400})
    assert "abcdefghij" in out
    out2 = r.run({"path": "b.txt", "max_chars": 8})
    assert "[harness:" in out2 or "harness" in out2


def test_read_file_rejects_directory(tmp_path: Path) -> None:
    (tmp_path / "d").mkdir()
    s = _scope(tmp_path)
    with pytest.raises(ValueError, match="not a file"):
        ReadFile(s).run({"path": "d"})


def test_list_files_and_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import harness.tools.fs.operations as ops

    monkeypatch.setattr(ops, "MAX_LIST_ENTRIES", 3)
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")
    s = _scope(tmp_path)
    out = ListFiles(s).run({"path": "."})
    assert "omitted" in out or "glob_files" in out
    assert out.count(".txt") >= 3


def test_path_stat(tmp_path: Path) -> None:
    f = tmp_path / "x.py"
    f.write_text("hi", encoding="utf-8")
    s = _scope(tmp_path)
    out = PathStat(s).run({"path": "x.py"})
    assert "size: 2" in out
    assert "is_file: True" in out


def test_glob_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("1", encoding="utf-8")
    (tmp_path / "src" / "b.md").write_text("2", encoding="utf-8")
    s = _scope(tmp_path)
    out = GlobFiles(s).run({"pattern": "**/*.py", "root": "."})
    assert "src/a.py" in out.splitlines()


def test_mkdir_edit_write(tmp_path: Path) -> None:
    s = _scope(tmp_path)
    assert "ok" in Mkdir(s).run({"path": "nested/dir"})
    EditFile(s).run({"path": "nested/dir/f.txt", "old_str": "", "new_str": "alpha"})
    assert ReadFile(s).run({"path": "nested/dir/f.txt"}) == "alpha"
    WriteFile(s).run({"path": "nested/dir/f.txt", "content": "beta", "must_exist": True})
    assert ReadFile(s).run({"path": "nested/dir/f.txt"}) == "beta"
    with pytest.raises(FileExistsError):
        WriteFile(s).run({"path": "nested/dir/f.txt", "content": "x", "create_only": True})


def test_delete_move_copy(tmp_path: Path) -> None:
    s = _scope(tmp_path)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    with pytest.raises(ValueError, match="confirm"):
        DeletePath(s).run({"path": "a.txt", "confirm": False})
    assert DeletePath(s).run({"path": "a.txt", "confirm": True}).startswith("delete")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    MovePath(s).run(
        {"from_path": "b.txt", "to_path": "c.txt", "confirm": True}
    )
    assert (tmp_path / "c.txt").read_text() == "b"
    CopyPath(s).run({"from_path": "c.txt", "to_path": "d.txt"})
    assert (tmp_path / "d.txt").read_text() == "b"


def test_copy_tree(tmp_path: Path) -> None:
    s = _scope(tmp_path)
    (tmp_path / "t1").mkdir()
    (tmp_path / "t1" / "f.txt").write_text("z", encoding="utf-8")
    CopyPath(s).run({"from_path": "t1", "to_path": "t2", "recursive": True})
    assert (tmp_path / "t2" / "f.txt").read_text() == "z"


def test_grep_python_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("harness.tools.fs.grep_tool.shutil.which", lambda *_: None)
    (tmp_path / "m.py").write_text("foo = 1\nbar = 2\n", encoding="utf-8")
    s = _scope(tmp_path)
    out = GrepWorkspace(s).run({"pattern": r"foo\s*=", "path": ".", "glob": "*.py"})
    assert "m.py" in out
    assert "foo" in out


def test_grep_invalid_regex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("harness.tools.fs.grep_tool.shutil.which", lambda *_: None)
    s = _scope(tmp_path)
    with pytest.raises(ValueError, match="invalid regex"):
        GrepWorkspace(s).run({"pattern": "("})


def test_execute_unknown_tool(tmp_path: Path) -> None:
    s = _scope(tmp_path)
    reg = {"read_file": ReadFile(s)}
    res = execute(ToolCall(name="missing", args={}), reg)
    assert res.is_error
