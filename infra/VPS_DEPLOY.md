# Evo Garden VPS Deployment

## Server Setup (Ubuntu 22.04+)

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Create app user
adduser --disabled-password --gecos "" evogarden
usermod -aG sudo evogarden

# Install dependencies
apt update && apt install -y python3.11 python3.11-venv python3-pip nginx git certbot nodejs npm

# Clone repo (as evogarden user)
su - evogarden
git clone https://gitlawb.com/your-username/evo-garden.git /opt/evo-garden
cd /opt/evo-garden

# Set up Python venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build the website
cd web && npm install && npm run build && cd ..

# Create config
cp config.example.yaml config.yaml
# Edit config.yaml with your settings
nano config.yaml
```

## Systemd Service (Agent)

```bash
sudo cp infra/evo-garden.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable evo-garden
sudo systemctl start evo-garden
```

## Systemd Service (Web Server)

```bash
sudo cp infra/evo-garden-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable evo-garden-web
sudo systemctl start evo-garden-web
```

## Nginx Reverse Proxy

```bash
sudo cp infra/nginx.conf /etc/nginx/sites-available/evo-garden
sudo ln -s /etc/nginx/sites-available/evo-garden /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL
sudo certbot --nginx -d evo-garden.yourdomain.com
```

## GitLawb CI/CD Variables

In GitLawb → Settings → CI/CD → Variables:

| Variable | Value | Protected |
|---|---|---|
| `LLM_API_KEY` | your-llm-api-key | Yes |
| `SSH_PRIVATE_KEY` | your-private-key | Yes |
| `VPS_HOST` | your-vps-ip | Yes |
| `VPS_USER` | evogarden | Yes |
| `GITLAWB_TOKEN` | your-gitlawb-token | Yes |

## Evolution Schedule

In GitLawb → CI/CD → Schedules:

Create a schedule to trigger evolution:
- **Cron pattern**: `0 */2 * * *` (every 2 hours)
- **Target branch**: main
- **Variable**: `EVO_MODE=ci`
