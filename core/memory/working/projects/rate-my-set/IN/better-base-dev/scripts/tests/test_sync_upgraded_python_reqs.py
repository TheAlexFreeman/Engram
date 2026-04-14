from __future__ import annotations

from pathlib import Path

from scripts.sync_upgraded_python_reqs import Handler


def _make_handler(
    *,
    latest_versions: dict[str, str],
    dependency_strings: list[str],
    pyproject: dict | None = None,
) -> Handler:
    handler = Handler()
    handler.__dict__["latest_versions"] = latest_versions
    handler.__dict__["dependency_strings"] = dependency_strings
    if pyproject is None:
        pyproject = {"project": {"dependencies": dependency_strings}}
    handler.__dict__["pyproject"] = pyproject
    return handler


def test_replace_references_updates_extras_and_markers() -> None:
    django_storages = "django-storages[s3]==1.14.5"
    psycopg = "psycopg[c]==3.3.1; sys_platform != 'win32' and sys_platform != 'darwin'"

    handler = _make_handler(
        latest_versions={
            "django-storages": "1.14.6",
            "psycopg": "3.3.2",
        },
        dependency_strings=[django_storages, psycopg],
    )

    contents = f'''prod = [
    "{django_storages}",
    "{psycopg}",
]\n'''

    final_contents = handler.replace_references(contents)

    assert '"django-storages[s3]==1.14.6"' in final_contents
    assert (
        "\"psycopg[c]==3.3.2; sys_platform != 'win32' and sys_platform != 'darwin'\""
        in final_contents
    )


def test_replace_references_normalizes_underscore_and_hyphen_package_names() -> None:
    dependency = "some_package==1.0.0"

    handler = _make_handler(
        latest_versions={"some-package": "2.0.0"},
        dependency_strings=[dependency],
    )

    contents = f'project = ["{dependency}"]\n'
    final_contents = handler.replace_references(contents)

    assert '"some_package==2.0.0"' in final_contents


def test_replace_references_skips_non_pinned_and_wildcard_versions() -> None:
    non_pinned = "django>=5.2"
    wildcard_pinned = "django==5.*"

    handler = _make_handler(
        latest_versions={"django": "5.2.11"},
        dependency_strings=[non_pinned, wildcard_pinned],
    )

    contents = f'''project = [
    "{non_pinned}",
    "{wildcard_pinned}",
]\n'''

    final_contents = handler.replace_references(contents)

    assert final_contents == contents


def test_format_toml_uses_project_taplo_command(monkeypatch) -> None:
    called_commands: list[list[str]] = []

    def _fake_run(command: list[str], *, check: bool) -> None:
        assert check is True
        called_commands.append(command)

    monkeypatch.setattr("scripts.sync_upgraded_python_reqs.subprocess.run", _fake_run)

    handler = Handler()
    handler.format_toml(Path("pyproject.toml"))

    assert called_commands == [["bun", "run", "fmt:toml", "--", "pyproject.toml"]]


def test_replace_pre_commit_django_target_versions_syncs_django_hooks() -> None:
    handler = _make_handler(
        latest_versions={"django": "6.0.3"},
        dependency_strings=["django==6.0.3"],
    )

    contents = """repos:
  - repo: https://github.com/adamchainz/djade-pre-commit
    hooks:
      - id: djade
        args: [--target-version, "5.2"]
  - repo: https://github.com/adamchainz/django-upgrade
    hooks:
      - id: django-upgrade
        args: ["--target-version", "5.2"]
"""

    final_contents = handler.replace_pre_commit_django_target_versions(contents)

    assert 'args: [--target-version, "6.0"]' in final_contents
    assert 'args: ["--target-version", "6.0"]' in final_contents
