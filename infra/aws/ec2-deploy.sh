#!/usr/bin/env bash
set -euo pipefail

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip nginx certbot python3-certbot-nginx unzip curl

if ! command -v aws >/dev/null 2>&1; then
  curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp
  /tmp/aws/install
fi

id -u prism >/dev/null 2>&1 || useradd --system --home-dir /opt/prism --shell /usr/sbin/nologin prism
install -d -o prism -g prism /opt/prism /etc/prism
aws s3 cp "s3://$1/releases/backend.tar.gz" /tmp/prism-backend.tar.gz --region ap-south-1
tar -xzf /tmp/prism-backend.tar.gz -C /opt/prism
chown -R prism:prism /opt/prism
python3 -m venv /opt/prism/venv
/opt/prism/venv/bin/pip install --no-cache-dir -r /opt/prism/backend/requirements.txt
install -m 0755 /opt/prism/infra/aws/asm-exec /usr/local/bin/asm-exec

printf 'AWS_REGION=ap-south-1\nAWS_DEFAULT_REGION=ap-south-1\nPRISM_DB_HOST=%s\nPRISM_APP_SECRET_JSON={{resolve:secretsmanager:prism/backend:SecretString}}\nPRISM_DB_SECRET_JSON={{resolve:secretsmanager:%s:SecretString}}\nSTORAGE_BACKEND=s3\nS3_BUCKET_NAME=%s\nAUTH_FRONTEND_URL=https://prism.amaankhan.in\nCORS_ALLOWED_ORIGINS=["https://prism.amaankhan.in"]\nGITHUB_OAUTH_CALLBACK_URL=https://api.amaankhan.in/auth/github/callback\nGITHUB_APP_SETUP_URL=https://api.amaankhan.in/auth/github/install/callback\nAUTH_COOKIE_SECURE=true\n' "$2" "$3" "$1" > /etc/prism/prism.env
chmod 0600 /etc/prism/prism.env

cat > /etc/systemd/system/prism-api.service <<'EOF'
[Unit]
Description=PRism FastAPI backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=prism
Group=prism
WorkingDirectory=/opt/prism/backend
RuntimeDirectory=prism
EnvironmentFile=/etc/prism/prism.env
ExecStart=/usr/local/bin/asm-exec -- /opt/prism/venv/bin/python /opt/prism/backend/deploy/start.py
Restart=always
RestartSec=10
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/run/prism
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/nginx/sites-available/prism-api <<'EOF'
server {
    listen 80;
    server_name api.amaankhan.in;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }
}
EOF
ln -sf /etc/nginx/sites-available/prism-api /etc/nginx/sites-enabled/prism-api
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx prism-api
systemctl reload nginx
