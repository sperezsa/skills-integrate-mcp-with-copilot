"""Create or update a teacher account for the activities application."""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile

from app import PASSWORD_HASH_ITERATIONS, TEACHERS_FILE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="Teacher username to create or update")
    username = parser.parse_args().username.strip()
    if not username:
        parser.error("username must not be empty")

    try:
        with TEACHERS_FILE.open(encoding="utf-8") as account_file:
            accounts = json.load(account_file)
    except FileNotFoundError:
        accounts = {}
    if not isinstance(accounts, dict):
        raise ValueError(f"{TEACHERS_FILE} must contain a JSON object")

    password = getpass.getpass("Teacher password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")

    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    accounts[username] = {"salt": salt.hex(), "password_hash": password_hash}

    TEACHERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=TEACHERS_FILE.parent,
            prefix=".teachers-",
            suffix=".tmp",
            delete=False,
        ) as account_file:
            temporary_path = Path(account_file.name)
            json.dump(accounts, account_file, indent=2)
            account_file.write("\n")
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, TEACHERS_FILE)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()

    print(f"Teacher account {username!r} saved to {TEACHERS_FILE}")


if __name__ == "__main__":
    main()
