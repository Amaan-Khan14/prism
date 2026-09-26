"""Resolve deployment settings, apply migrations, and start the API."""

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import URL


def main() -> None:
    app_secrets = json.loads(os.environ.pop("PRISM_APP_SECRET_JSON"))
    database_secrets = json.loads(os.environ.pop("PRISM_DB_SECRET_JSON"))

    private_key = app_secrets.pop("GITHUB_PRIVATE_KEY")
    key_path = Path("/run/prism/github-app.pem")
    key_path.write_text(private_key)
    key_path.chmod(0o600)
    os.environ["GITHUB_PRIVATE_KEY_PATH"] = str(key_path)

    for key, value in app_secrets.items():
        os.environ[key] = value

    os.environ["DATABASE_URL"] = URL.create(
        "postgresql+asyncpg",
        username=database_secrets["username"],
        password=database_secrets["password"],
        host=os.environ["PRISM_DB_HOST"],
        port=5432,
        database="prism",
    ).render_as_string(hide_password=False)

    subprocess.run(["/opt/prism/venv/bin/alembic", "upgrade", "head"], check=True)
    os.execv(
        "/opt/prism/venv/bin/uvicorn",
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    )


if __name__ == "__main__":
    main()
