from __future__ import annotations

from scripts.upgrade_python_reqs import Handler


def _make_handler(pyproject: dict) -> Handler:
    handler = Handler()
    handler.__dict__["pyproject"] = pyproject
    return handler


def test_dependency_entries_extract_names_from_extras_and_markers() -> None:
    handler = _make_handler(
        {
            "project": {
                "dependencies": [
                    "mypy[faster-cache]==1.19.1",
                    "django==5.2.11",
                ]
            },
            "dependency-groups": {
                "prod": [
                    "django-storages[s3]==1.14.6",
                    "psycopg[c]==3.3.2; sys_platform != 'win32' and sys_platform != 'darwin'",
                ]
            },
        }
    )

    entries = list(handler.dependency_entries)

    assert [entry.package for entry in entries] == [
        "mypy",
        "django",
        "django-storages",
        "psycopg",
    ]


def test_upgrade_entries_dedupes_normalized_package_names(monkeypatch) -> None:
    handler = _make_handler(
        {
            "project": {
                "dependencies": [
                    "some-package==1.0.0",
                    "some_package==1.0.0",
                    "other.pkg==2.0.0",
                ]
            },
            "dependency-groups": {},
        }
    )

    called_commands: list[list[str]] = []

    def _fake_run(command: list[str], *, check: bool) -> None:
        assert check is True
        called_commands.append(command)

    monkeypatch.setattr("scripts.upgrade_python_reqs.subprocess.run", _fake_run)

    handler.upgrade_entries()

    installed_packages = [command[-1] for command in called_commands]
    assert set(installed_packages) == {"some-package", "other.pkg"}
    assert len(installed_packages) == 2
