# PRism API deployment

The AWS deployment uses three PRism CloudFormation stacks in `ap-south-1`:

| Stack | Purpose |
| --- | --- |
| `prism-deployer-bootstrap` | A bootstrap IAM user that may assume the PRism deployer role, plus the deployer role. |
| `prism-ip` | Retained Elastic IP for `api.amaankhan.in`. |
| `prism-api` | Dedicated VPC, private single-AZ RDS PostgreSQL, EC2, and bucket-scoped runtime IAM role. |

The artifact bucket is the existing `prism-artifact-storage` stack. The backend release is stored at `s3://prism-artifact-storage-prismartifactbucket-ubri8x7giofh/releases/backend.tar.gz`; it contains source and deployment helpers, never `.env` or the GitHub private key. `publish-secret.py` transfers the local backend credentials into the project-scoped `prism/backend` Secrets Manager secret through a mode-0600 temporary file. Runtime secrets are referenced by `asm-exec` and resolved in the EC2 process environment.

When packaging on macOS, use `COPYFILE_DISABLE=1 tar --exclude='._*'` so AppleDouble files are omitted. Alembic scans migration filenames and will attempt to import a `._*.py` file if one is present.

EC2 runs the API as a systemd service behind Nginx and exposes ports 80 and 443 only. RDS is in private subnets and accepts port 5432 only from the API security group. S3 objects are private; the instance role is scoped to this bucket's objects. The database has one day of automated backup retention because this account's free-tier plan rejected seven days. The database and Elastic IP are retained on stack deletion.

DNS record: `A api.amaankhan.in -> 13.203.109.219` with a short TTL. Once DNS resolves and the API responds over HTTP, install the certificate on the instance using `certbot --nginx -d api.amaankhan.in --non-interactive --agree-tos --register-unsafely-without-email --redirect`.

The GitHub App's callback URL must include `https://api.amaankhan.in/auth/github/callback`. Its setup URL, if enabled, is `https://api.amaankhan.in/auth/github/install/callback`. The frontend should set `NEXT_PUBLIC_API_URL=https://api.amaankhan.in` when deployed to `https://prism.amaankhan.in`.

`asm-exec` is copied unmodified from [AWS Agent Toolkit](https://github.com/aws/agent-toolkit-for-aws/blob/main/plugins/aws-core/skills/aws-secrets-manager/references/asm-exec), SHA-256 `05a9f8164b63b286bcf88bf4223c95b799e0ecaada45ddcd805567f57b20299f`. It is distributed under [Apache 2.0](ASM-EXEC-LICENSE); see [NOTICE](ASM-EXEC-NOTICE).
