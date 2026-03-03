# imagin-virtualization-platform

## Installation

### Development
1. Ensure Python is installed.
2. Install backend dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Launch the backend API:
   ```bash
   python backend/main.py
   ```
4. Install the Godot Engine (download from the official site) if you don’t have it yet.
5. Open the Godot project located in the `frontend` folder to run the frontend.

### Production (Docker Compose + HTTPS)
This setup serves the frontend and backend behind Traefik with TLS termination.

1. Prerequisites:
   - Docker and Docker Compose installed on the VPS.
   - A domain name pointing to your VPS public IP (A/AAAA DNS record).
   - A wildcard DNS record for app endpoints (for example `*.apps.your-domain.com`).
   - TLS certificate and key files for your domain.
2. Configure domain variable:
   ```bash
   cp .env.example .env
   sed -i 's/^DOMAIN_NAME=.*/DOMAIN_NAME=your-domain.com/' .env
   # Optional: override if you do not use apps.<DOMAIN_NAME>
   # echo "APPS_BASE_DOMAIN=apps.your-domain.com" >> .env
   cat .env
   ```
3. Install TLS certificate files:
   - Place your certificate chain at `traefik/certs/fullchain.pem`.
   - Place your private key at `traefik/certs/privkey.pem`.
4. Start the stack:
   ```bash
   docker compose up -d --build
   ```
5. Ensure ports `80` and `443` are open in your VPS firewall/security group.
6. Open `https://your-domain.com` in your browser.

Notes:
- HTTP traffic is redirected to HTTPS automatically.
- Frontend API calls are configured from `DOMAIN_NAME` and routed through Traefik at `https://<DOMAIN_NAME>/api/`.
- Cluster web UIs (for example Headlamp) are exposed through dynamic Traefik routes on `https://<generated-subdomain>.<APPS_BASE_DOMAIN>`.
