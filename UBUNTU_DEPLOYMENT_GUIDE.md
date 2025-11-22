# 🚀 Ubuntu Server Deployment Guide (Docker)

## 📋 Prerequisites

- Ubuntu 20.04+ server with SSH access
- Docker and Docker Compose installed
- Basic terminal knowledge

---

## Step 1: Connect to Your Server

```bash
# From your local machine, connect via SSH
ssh username@your-server-ip

# Example:
ssh ubuntu@192.168.1.100
```

---

## Step 2: Install Docker & Docker Compose

```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (so you don't need sudo)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in (or run: newgrp docker)
exit
# Then SSH back in

# Verify installation
docker --version
docker-compose --version
```

---

## Step 3: Clone Your Project

```bash
# Navigate to a directory (e.g., /opt or /home/ubuntu)
cd /opt
# OR
cd ~

# Clone your repository
git clone https://github.com/your-username/your-repo-name.git Project_Up
cd Project_Up

# If you don't have Git, upload files via SCP (see Step 3b)
```

### Alternative: Upload Files via SCP (if no Git)

```bash
# From your LOCAL machine (not server)
# Create a zip of your project (excluding venv, node_modules, etc.)
# Then upload:

scp -r /path/to/Project_Up ubuntu@your-server-ip:/opt/
```

---

## Step 4: Upload Service Account Credentials

### Option A: Using SCP (Recommended)

```bash
# From your LOCAL machine, upload the credentials file
scp service-account-creds.json ubuntu@your-server-ip:/opt/Project_Up/

# Or if you're already in the project directory:
scp service-account-creds.json ubuntu@your-server-ip:/opt/Project_Up/
```

### Option B: Create File Directly on Server

```bash
# On the server, create the file
cd /opt/Project_Up
nano service-account-creds.json

# Paste your JSON credentials, then:
# Press Ctrl+X, then Y, then Enter to save
```

### Option C: Using VS Code Remote (Easiest)

1. Install "Remote - SSH" extension in VS Code
2. Connect to your server
3. Open the project folder
4. Create/edit `service-account-creds.json` directly

---

## Step 5: Create Environment File

```bash
# On the server, create .env file
cd /opt/Project_Up
nano .env
```

**Paste this content (adjust values):**

```bash
# Database
MYSQL_ROOT_PASSWORD=your_strong_root_password_here
MYSQL_PASSWORD=your_strong_db_password_here
MYSQL_USER=scheduling_user
MYSQL_DATABASE=scheduling_system

# Flask
SECRET_KEY=generate_a_random_secret_key_here_min_32_chars
JWT_SECRET_KEY=generate_another_random_secret_key_here_min_32_chars
FLASK_ENV=production

# Google Sheets (path inside Docker container)
GOOGLE_APPLICATION_CREDENTIALS=/app/service-account-creds.json

# Celery/Redis
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

**Generate random secrets:**
```bash
# On the server, generate random keys:
openssl rand -hex 32  # Use this for SECRET_KEY
openssl rand -hex 32  # Use this for JWT_SECRET_KEY
```

**Save:** Press `Ctrl+X`, then `Y`, then `Enter`

---

## Step 6: Update Docker Compose for Production

```bash
# Check docker-compose.prod.yml exists
ls -la docker-compose.prod.yml

# If it doesn't exist, we'll use docker-compose.yml with environment variables
```

**Verify the production compose file mounts the credentials:**

The `docker-compose.prod.yml` should have:
```yaml
backend:
  volumes:
    - ./service-account-creds.json:/app/service-account-creds.json:ro
```

If not, we'll add it in Step 7.

---

## Step 7: Start Docker Containers

```bash
# Make sure you're in the project directory
cd /opt/Project_Up

# Build and start all services (production mode)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Watch logs (optional, press Ctrl+C to exit)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
```

**What this does:**
- Builds all Docker images
- Starts MySQL, Redis, Backend, Frontend, Celery workers
- Runs in background (`-d` flag)

---

## Step 8: Run Database Migrations

```bash
# Wait 30 seconds for MySQL to be ready, then run migrations
sleep 30

# Run migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head

# You should see: "Running upgrade ... -> ..., Add ..."
```

---

## Step 9: Verify Services Are Running

```bash
# Check all containers are running
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Should show: mysql, redis, backend, frontend, celery-worker, celery-beat (all "Up")

# Check backend health
curl http://localhost:8000/api/v1/health

# Should return: {"status": "healthy"} or similar
```

---

## Step 10: Configure Firewall (if needed)

```bash
# Allow HTTP (port 80) and HTTPS (port 443)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow SSH (if not already allowed)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

---

## Step 11: Set Up Reverse Proxy (Nginx) - Optional but Recommended

```bash
# Install Nginx
sudo apt install nginx -y

# Create Nginx config
sudo nano /etc/nginx/sites-available/scheduling-app
```

**Paste this configuration:**

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Change to your domain or IP

    # Frontend
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable the site:**
```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/scheduling-app /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## Step 12: Trigger Initial Sync

```bash
# Trigger Google Sheets sync
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python trigger_sync.py

# OR use the API endpoint
curl -X POST http://localhost:8000/api/v1/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Step 13: Access Your Application

### From Browser:
- **Frontend:** `http://your-server-ip` or `http://your-domain.com`
- **Backend API:** `http://your-server-ip:8000/api/v1/` or `http://your-domain.com/api/v1/`
- **Health Check:** `http://your-server-ip:8000/api/v1/health`

---

## 🔧 Common Commands

### View Logs
```bash
# All services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f mysql
```

### Restart Services
```bash
# Restart all
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart

# Restart specific service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart backend
```

### Stop Services
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
```

### Start Services
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Update Code
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## 🐛 Troubleshooting

### Containers Not Starting
```bash
# Check logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs

# Check container status
docker ps -a
```

### Database Connection Errors
```bash
# Check MySQL is running
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps mysql

# Check MySQL logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs mysql
```

### Credentials File Not Found
```bash
# Verify file exists
ls -la /opt/Project_Up/service-account-creds.json

# Check Docker can see it
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend ls -la /app/service-account-creds.json
```

### Port Already in Use
```bash
# Check what's using port 80
sudo lsof -i :80

# Check what's using port 8000
sudo lsof -i :8000

# Stop conflicting services or change ports in docker-compose.yml
```

---

## 🔐 Security Checklist

- [ ] Changed all default passwords in `.env`
- [ ] Generated strong random secrets
- [ ] `service-account-creds.json` is NOT in Git
- [ ] Firewall is configured
- [ ] Using HTTPS (set up SSL certificate)
- [ ] Regular backups of database

---

## 📝 Quick Reference

**Project Location:** `/opt/Project_Up` (or `~/Project_Up`)

**Key Files:**
- `.env` - Environment variables
- `service-account-creds.json` - Google credentials
- `docker-compose.yml` - Base configuration
- `docker-compose.prod.yml` - Production overrides

**Important Commands:**
```bash
# Start
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Stop
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## ✅ Deployment Complete!

Your application should now be running at:
- **Frontend:** `http://your-server-ip`
- **Backend:** `http://your-server-ip:8000`

**Next Steps:**
1. Set up SSL certificate (Let's Encrypt)
2. Configure domain name
3. Set up automated backups
4. Monitor logs regularly

---

**Need Help?** Check logs first: `docker-compose logs -f`

