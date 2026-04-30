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
   - TLS certificate and key files for your domain.
2. Configure domain variable:
   ```bash
   cp .env.example .env
   sed -i 's/^DOMAIN_NAME=.*/DOMAIN_NAME=your-domain.com/' .env
   # Optional: override endpoint path prefix
   # echo "ENDPOINT_PATH_BASE=/endpoints" >> .env
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
- Cluster web UIs (for example Headlamp) are exposed through dynamic Traefik routes on `https://<DOMAIN_NAME>/endpoints/<endpoint-id>/`.
- Existing cluster endpoint records are reconciled automatically when the backend container starts.

## 5G provision — host prerequisites

The `free5gc` provision deploys the free5gc 5G core, UERANSIM (gNB + UE simulator), and the free5gc web console onto a K3D cluster via the `towards5gs` Helm charts. free5gc's UPF needs the out-of-tree **`gtp5g`** kernel module, so the **Docker host kernel** must have it loaded *before* you create the infra.

**Supported host:** Linux only. Docker Desktop (LinuxKit kernel) is not supported. WSL2 works only if you build and boot a custom WSL2 kernel (see "WSL2" below).

### Linux host

Run once per host (and again after every kernel upgrade):

```bash
# 1. SCTP is used by N2 (gNB ↔ AMF)
sudo modprobe sctp

# 2. Build and install gtp5g (matches free5gc 4.x — pin to the tag that the
#    towards5gs chart version you deploy expects)
sudo apt-get update && sudo apt-get install -y git build-essential linux-headers-$(uname -r)
git clone -b v0.8.10 https://github.com/free5gc/gtp5g.git
cd gtp5g
make
sudo make install
sudo modprobe gtp5g

# 3. Verify
lsmod | grep gtp5g     # gtp5g loaded
lsmod | grep sctp      # sctp loaded
```

Persist across reboots:

```bash
echo gtp5g | sudo tee /etc/modules-load.d/gtp5g.conf
echo sctp  | sudo tee /etc/modules-load.d/sctp.conf
```

### WSL2 (Windows host)

The default WSL2 kernel does not include `gtp5g`. Build a custom WSL2 kernel that has it, then point WSL at it:

1. Inside a WSL2 Ubuntu distro, clone Microsoft's kernel sources at the tag matching `uname -r`, build with `Microsoft/config-wsl`, and build `gtp5g` out-of-tree against that kernel tree.
2. Copy the resulting `bzImage` to a Windows path and reference it from `%USERPROFILE%\.wslconfig`:
   ```ini
   [wsl2]
   kernel=C:\\path\\to\\bzImage
   ```
3. `wsl --shutdown`, then restart and `sudo insmod gtp5g.ko` inside the distro.
4. Run Docker Engine **inside that same WSL2 distro** (not Docker Desktop) so the engine's containers share the custom kernel.

### Cluster requirements (handled automatically)

- **Multus CNI** — auto-applied by the provisioner if absent (free5gc needs multiple network interfaces per pod).
- **NodePort for the web console** — the provisioner appends the configured `web_console_port` (default `30500`) to the K3D cluster's port mapping before cluster creation.
- **`helm` CLI** — installed in the backend image by the Dockerfile.

### Launching a 5G infra

Once the host kernel is ready, create the infra via `POST /api/infra/create`:

```json
{
  "project_id": 1,
  "infra_type": "cluster",
  "infra_config": { "name": "my-5g", "node_count": 2, "ports": [] },
  "provisions": [
    { "type": "headlamp", "config": { "port": 30080 } },
    { "type": "free5gc",  "config": { "deploy_ueransim": true, "web_console_port": 30500 } }
  ]
}
```

Returns `200 OK` once `helm install --wait` completes (~5–7 min). The free5gc web console URL is exposed at `provisions[].state.web_console.url` in `GET /api/infra/fetch`.
