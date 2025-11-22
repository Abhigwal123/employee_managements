#!/bin/bash
# Quick Deployment Script for Ubuntu Server
# Usage: ./DEPLOY_QUICK.sh

set -e  # Exit on error

echo "=========================================="
echo "  Smart Scheduling System - Quick Deploy"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run as root. Use a regular user with sudo access.${NC}"
   exit 1
fi

# Step 1: Check Docker
echo -e "${YELLOW}Step 1: Checking Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Installing...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo -e "${GREEN}Docker installed. Please log out and back in, then run this script again.${NC}"
    exit 0
fi
echo -e "${GREEN}✓ Docker is installed${NC}"

# Step 2: Check Docker Compose
echo -e "${YELLOW}Step 2: Checking Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Installing Docker Compose...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi
echo -e "${GREEN}✓ Docker Compose is installed${NC}"

# Step 3: Check for service-account-creds.json
echo -e "${YELLOW}Step 3: Checking for credentials file...${NC}"
if [ ! -f "service-account-creds.json" ]; then
    echo -e "${RED}⚠️  service-account-creds.json not found!${NC}"
    echo -e "${YELLOW}Please upload it using:${NC}"
    echo -e "  scp service-account-creds.json $USER@$(hostname -I | awk '{print $1}'):$(pwd)/"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ Credentials file found${NC}"
fi

# Step 4: Check for .env file
echo -e "${YELLOW}Step 4: Checking for .env file...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cat > .env << 'EOF'
# Database
MYSQL_ROOT_PASSWORD=change_me_root_password
MYSQL_PASSWORD=change_me_db_password
MYSQL_USER=scheduling_user
MYSQL_DATABASE=scheduling_system

# Flask
SECRET_KEY=change_me_secret_key_min_32_chars
JWT_SECRET_KEY=change_me_jwt_secret_min_32_chars
FLASK_ENV=production

# Google Sheets
GOOGLE_APPLICATION_CREDENTIALS=/app/service-account-creds.json

# Celery/Redis
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
EOF
    echo -e "${RED}⚠️  .env file created with default values.${NC}"
    echo -e "${YELLOW}Please edit .env and change the passwords and secrets!${NC}"
    echo -e "${YELLOW}Press Enter to continue after editing...${NC}"
    read
else
    echo -e "${GREEN}✓ .env file found${NC}"
fi

# Step 5: Stop existing containers
echo -e "${YELLOW}Step 5: Stopping existing containers...${NC}"
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down 2>/dev/null || true

# Step 6: Build and start
echo -e "${YELLOW}Step 6: Building and starting containers...${NC}"
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Step 7: Wait for MySQL
echo -e "${YELLOW}Step 7: Waiting for MySQL to be ready...${NC}"
MAX_WAIT=60
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T mysql mysqladmin ping -h localhost -uroot -prootpassword &>/dev/null 2>&1; then
        echo -e "${GREEN}✓ MySQL is ready${NC}"
        break
    fi
    echo -n "."
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done
echo ""

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo -e "${RED}MySQL did not start in time. Check logs: docker-compose logs mysql${NC}"
    exit 1
fi

# Step 8: Run migrations
echo -e "${YELLOW}Step 8: Running database migrations...${NC}"
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend alembic upgrade head || {
    echo -e "${YELLOW}⚠️  Migration failed or already applied${NC}"
}

# Step 9: Verify services
echo -e "${YELLOW}Step 9: Verifying services...${NC}"
sleep 5

if curl -f http://localhost:8000/api/v1/health &>/dev/null; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  Backend health check failed. Check logs: docker-compose logs backend${NC}"
fi

# Step 10: Show status
echo ""
echo -e "${GREEN}=========================================="
echo -e "  Deployment Complete!"
echo -e "==========================================${NC}"
echo ""
echo "Services:"
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
echo ""
echo "Access your application:"
echo "  - Frontend: http://$(hostname -I | awk '{print $1}')"
echo "  - Backend:  http://$(hostname -I | awk '{print $1}'):8000/api/v1/"
echo "  - Health:   http://$(hostname -I | awk '{print $1}'):8000/api/v1/health"
echo ""
echo "Next steps:"
echo "  1. Trigger sync: docker-compose exec backend python trigger_sync.py"
echo "  2. View logs: docker-compose logs -f"
echo ""

