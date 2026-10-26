# Self-Hosting & Remote Access Guide

Paslood is built local-first and privacy-respecting. You can run it on your local workstation, in a Docker container on a home server (NAS, Raspberry Pi, NUC), or deploy it to a private cloud instance.

This guide covers running Paslood containerized and securely accessing it from your smartphone or anywhere in the world.

---

## 1. Quickstart: Running via Docker

### Requirements
- Docker Engine $\ge 24.0$ & Docker Compose $\ge 2.20$

### Setup
1. Clone the repository or download `docker-compose.yml` and `.env.example`:
   ```bash
   git clone https://github.com/tiwu/paslood.git
   cd paslood
   cp .env.example .env
   ```

2. Generate a secure secret key:
   ```bash
   openssl rand -hex 32
   ```
   Paste the generated value into `WEALTH_PILOT_SECRET_KEY` in `.env`.

3. Set your admin password:
   ```bash
   # Run the container once to set password
   docker compose run --rm paslood set-password
   ```

4. Start Paslood:
   ```bash
   docker compose up -d
   ```
   Access the dashboard at `http://localhost:8000`.

---

## 2. Remote Access Methods

To access Paslood from your phone or outside your home network, choose one of three supported methods:

| Method | Best For | Security | Public Port Required? |
| :--- | :--- | :--- | :--- |
| **Tailscale** *(Recommended)* | Personal access from phone/laptop | Zero-Trust WireGuard Mesh | **No** (Most secure) |
| **Cloudflare Tunnel** | Access from any browser without VPN app | Zero-Trust HTTPS reverse proxy | **No** |
| **Dynamic DNS (DuckDNS + Caddy)** | Self-managed custom domain | Automatic Let's Encrypt TLS | Yes (Ports 80/443 forwarded) |

---

### Option A: Tailscale (Private Mesh — Recommended)

Tailscale connects your devices securely over an encrypted WireGuard mesh without exposing any open ports to the public internet.

1. Create a free account at [tailscale.com](https://tailscale.com).
2. Generate an Auth Key in **Tailscale Admin Console** $\rightarrow$ **Settings** $\rightarrow$ **Keys**.
3. In your `.env`:
   ```dotenv
   TAILSCALE_AUTHKEY=tskey-auth-...
   WEALTH_PILOT_TRUSTED_ORIGINS=https://paslood.your-tailnet.ts.net,http://paslood:8000
   ```
4. Start with the Tailscale profile:
   ```bash
   docker compose --profile tailscale up -d
   ```
5. Install Tailscale on your iPhone or Android. You can now access Paslood securely at `http://paslood:8000` (or `https://paslood.your-tailnet.ts.net` if MagicDNS HTTPS is enabled).

---

### Option B: Cloudflare Tunnel

Cloudflare Tunnel exposes your local service via Cloudflare's edge network without port forwarding on your home router.

1. In Cloudflare Zero Trust dashboard, go to **Networks** $\rightarrow$ **Tunnels** and create a tunnel.
2. Choose **Docker** as environment and copy the tunnel token.
3. In `.env`:
   ```dotenv
   CLOUDFLARE_TUNNEL_TOKEN=eyJh...
   WEALTH_PILOT_TRUSTED_ORIGINS=https://wealth.yourdomain.com
   ```
4. Route hostname `wealth.yourdomain.com` to `http://paslood:8000` in the Cloudflare dashboard.
5. Start:
   ```bash
   docker compose --profile cloudflared up -d
   ```

---

### Option C: Dynamic DNS (DuckDNS + Caddy)

For users with dynamic home IP addresses wanting direct HTTPS access:

1. Create a free domain at [duckdns.org](https://duckdns.org) (e.g. `mywealth.duckdns.org`).
2. Forward ports `80` and `443` on your home router to your Docker host.
3. In `.env`:
   ```dotenv
   DUCKDNS_DOMAIN=mywealth
   ACME_EMAIL=your-email@example.com
   WEALTH_PILOT_TRUSTED_ORIGINS=https://mywealth.duckdns.org
   ```
4. Start with the DDNS profile:
   ```bash
   docker compose --profile ddns up -d
   ```
   Caddy will automatically provision and renew a free Let's Encrypt TLS certificate.

---

## 3. Social OAuth Logins

You can enable seamless 1-click social logins alongside or instead of local password authentication:

### Google OAuth
1. Go to [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials).
2. Create an **OAuth 2.0 Client ID** (Web application).
3. Add Authorized redirect URI: `https://<your-domain>/auth/google/callback`.
4. Add credentials to `.env`:
   ```dotenv
   WEALTH_PILOT_GOOGLE_CLIENT_ID=...
   WEALTH_PILOT_GOOGLE_CLIENT_SECRET=...
   ```

### GitHub OAuth
1. In GitHub, go to **Settings** $\rightarrow$ **Developer settings** $\rightarrow$ **OAuth Apps** $\rightarrow$ **New OAuth App**.
2. Set Authorization callback URL: `https://<your-domain>/auth/github/callback`.
3. Add to `.env`:
   ```dotenv
   WEALTH_PILOT_GITHUB_CLIENT_ID=...
   WEALTH_PILOT_GITHUB_CLIENT_SECRET=...
   ```

### Whitelisting Emails
To restrict access strictly to you or family members:
```dotenv
WEALTH_PILOT_ALLOWED_EMAILS=alice@example.com,bob@example.com
```

---

## 4. Backups and Data Portability

All application data (portfolios, transaction cache, encrypted secrets, user database) lives inside the Docker volume `/data` (or your local directory `WEALTH_PILOT_DATA_DIR`).

### Taking a Backup
```bash
docker run --rm -v wealthpilot_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/paslood-backup-$(date +%Y%m%d).tar.gz -C /data .
```

### Restoring a Backup
```bash
docker run --rm -v wealthpilot_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/paslood-backup-YYYYMMDD.tar.gz -C /data
```
