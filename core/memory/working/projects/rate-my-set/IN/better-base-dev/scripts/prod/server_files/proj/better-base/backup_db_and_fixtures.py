#!/usr/bin/env python3
from __future__ import annotations

import datetime
import logging
import logging.handlers
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(kw_only=True)
class BackupPaths:
    nvme_backup_path: Path
    staged_backup_path: Path
    fixtures_path: Path

    @classmethod
    def create_default(cls) -> BackupPaths:
        nvme = Path("/home/ubuntu/backups/db")
        staged = Path("/home/ubuntu/backups/staged/db")
        fixtures_path = Path("/home/ubuntu/backups/fixtures/important-fixtures.json")
        return cls(
            nvme_backup_path=nvme,
            staged_backup_path=staged,
            fixtures_path=fixtures_path,
        )


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("backup_db_and_fixtures")
    logger.setLevel(logging.INFO)

    # Create a formatter.
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Set up the file handler to log to a rotating file.
    file_handler = logging.handlers.RotatingFileHandler(
        "/home/ubuntu/logs/backup_db_and_fixtures.log",
        maxBytes=1024 * 1024,  # 1MB
        backupCount=5,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Set up the console handler to log to stdout.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def run_command(cmd: str, logger: logging.Logger) -> None:
    logger.info(f"Running command: {cmd}")

    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # Line buffered
        universal_newlines=True,
    )

    # Read stdout and stderr in close to real-time.
    while True:
        stdout_line = process.stdout.readline() if process.stdout else ""
        stderr_line = process.stderr.readline() if process.stderr else ""

        if not stdout_line and not stderr_line:
            # If no output, sleep briefly to prevent unnecessary CPU usage.
            time.sleep(0.1)

        if stdout_line:
            logger.info(f"stdout: {stdout_line.rstrip()}")

        if stderr_line:
            logger.warning(f"stderr: {stderr_line.rstrip()}")

        # Break if process is done and no more output.
        if process.poll() is not None and not stdout_line and not stderr_line:
            break

    # Get the return code and handle errors.
    returncode = process.wait()
    if returncode != 0:
        logger.error(f"Command failed with exit code {returncode}")
        sys.exit(returncode)


def calculate_mod_suffix() -> int:
    start_date = datetime.date(2026, 1, 1)
    days = (datetime.date.today() - start_date).days
    return days % 3


def backup_database(paths: BackupPaths, logger: logging.Logger) -> None:
    # Step 1: Run the initial `pg_dump` command.
    initial_dump_path = paths.nvme_backup_path / "latest.dump"

    # Create the parent directory if it doesn't exist.
    initial_dump_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove the old file if it exists (use sudo since it may be owned by postgres).
    if initial_dump_path.exists():
        run_command(f"sudo rm -f {initial_dump_path}", logger)

    pg_dump_cmd = f"sudo -u postgres pg_dump -U postgres -d better_base_prod -Fc -Z 9 -f {initial_dump_path}"
    run_command(pg_dump_cmd, logger)

    # Change ownership back to ubuntu so future operations don't need sudo.
    run_command(f"sudo chown ubuntu:ubuntu {initial_dump_path}", logger)

    # Step 2: Export important fixtures.
    paths.fixtures_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        f"chmod +x {Path(__file__).parent}/backup_important_fixtures.py", logger
    )
    fixtures_cmd = f"({Path(__file__).parent}/backup_important_fixtures.py -p) > {paths.fixtures_path}"
    run_command(fixtures_cmd, logger)

    # Step 3: Ensure staged backup directory exists and then copy the dump file to HDD
    # with the mod suffix.
    paths.staged_backup_path.mkdir(parents=True, exist_ok=True)
    mod_suffix = calculate_mod_suffix()
    staged_dump = paths.staged_backup_path / f"mod-{mod_suffix}-latest.dump"
    cp_cmd = f"rsync -av --delete {initial_dump_path} {staged_dump}"
    run_command(cp_cmd, logger)

    # Step 4: Upload the fixtures file, now in the staged backup directory, to
    # Cloudflare R2 (will overwrite if it exists).
    #
    # # * DevOps_Server_Setup_TODO: Replace `--endpoint-url` with your correct/actual one.
    s3_fixtures_cmd = (
        f"aws s3 cp {paths.fixtures_path} "
        f"s3://better-base-backups/better-base-prod/{paths.fixtures_path.name} "
        "--endpoint-url=https://1a6c036f837deaf2f6f84e4abbb65c31.r2.cloudflarestorage.com"
    )
    run_command(s3_fixtures_cmd, logger)

    # Step 5: Upload the dump file, now on the HDD, to Cloudflare R2 (will overwrite if
    # it exists).
    #
    # # * DevOps_Server_Setup_TODO: Replace `--endpoint-url` with your correct/actual one.
    s3_cmd = (
        f"aws s3 cp {staged_dump} s3://better-base-backups/better-base-prod/{staged_dump.name} "
        "--endpoint-url=https://1a6c036f837deaf2f6f84e4abbb65c31.r2.cloudflarestorage.com"
    )
    run_command(s3_cmd, logger)


def main() -> int:
    logger = setup_logging()

    try:
        paths = BackupPaths.create_default()
        backup_database(paths, logger)
        logger.info("Backup completed successfully.")
        return 0
    except Exception as e:
        logger.exception(f"Backup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
