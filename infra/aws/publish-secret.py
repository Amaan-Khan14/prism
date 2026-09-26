"""Publish local PRism credentials to the project-scoped AWS secret.

The secret is passed to AWS CLI through a mode-0600 temporary file. Values are
never printed or supplied on a command line.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[2]
values = dotenv_values(ROOT / "backend/.env")
required = (
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "GITHUB_APP_ID",
    "GITHUB_APP_CLIENT_ID",
    "GITHUB_APP_CLIENT_SECRET",
    "AUTH_SESSION_SECRET",
    "GITHUB_TOKEN_ENCRYPTION_KEY",
)
missing = [key for key in required if not values.get(key)]
if missing:
    raise SystemExit(f"Missing local configuration keys: {', '.join(missing)}")

key_path = Path(values.get("GITHUB_PRIVATE_KEY_PATH") or "")
if not key_path.is_file():
    raise SystemExit("GitHub App private key file is missing")

payload = {key: values[key] for key in required}
payload["GITHUB_PRIVATE_KEY"] = key_path.read_text()
for optional in ("REVIEW_PROVIDER", "GEMINI_MODEL", "GEMINI_FALLBACK_MODEL", "GEMINI_THINKING_LEVEL", "OPENAI_MODEL", "GITHUB_APP_SLUG"):
    if values.get(optional):
        payload[optional] = values[optional]

fd, filename = tempfile.mkstemp(prefix="prism-secret-", suffix=".json")
try:
    with os.fdopen(fd, "w") as output:
        json.dump(payload, output)
    common = ["aws", "secretsmanager", "--profile", "prism-deployer", "--region", "ap-south-1"]
    check = subprocess.run(
        common[:2] + ["describe-secret"] + common[2:] + ["--secret-id", "prism/backend"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if check.returncode == 0:
        action = "put-secret-value"
        args = ["--secret-id", "prism/backend"]
    else:
        action = "create-secret"
        args = ["--name", "prism/backend", "--tags", "Key=Project,Value=PRism"]
    subprocess.run(
        common[:2] + [action] + common[2:] + args + ["--secret-string", f"file://{filename}"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    print("Published PRism backend secret metadata successfully")
finally:
    os.unlink(filename)
