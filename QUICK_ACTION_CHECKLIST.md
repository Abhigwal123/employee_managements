# 🚀 Quick Action Checklist for GitHub Deployment

## ⚠️ CRITICAL: Security First

### Step 1: Check if Credentials Are Already in Git History
```bash
# Check if service-account-creds.json was ever committed
git log --all --full-history -- service-account-creds.json

# If found, ROTATE CREDENTIALS IMMEDIATELY:
# 1. Generate new service account key in Google Cloud Console
# 2. Update service-account-creds.json locally
# 3. Revoke old key in Google Cloud Console
# 4. Remove from Git history (if needed):
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch service-account-creds.json" \
  --prune-empty --tag-name-filter cat -- --all
```

### Step 2: Create Example Files
```bash
# Create template for credentials
cp service-account-creds.json service-account-creds.json.example
# Edit service-account-creds.json.example and replace real values with placeholders

# Create .env.example
cat > .env.example << EOF
# Database
MYSQL_ROOT_PASSWORD=your_root_password_here
MYSQL_PASSWORD=your_db_password_here
MYSQL_USER=scheduling_user
MYSQL_DATABASE=scheduling_system

# Flask
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_here
FLASK_ENV=development

# Google Sheets
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-creds.json
GOOGLE_INPUT_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
GOOGLE_OUTPUT_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit

# Celery/Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
EOF
```

---

## 🧹 Cleanup Before First Commit

### Step 3: Remove Files That Shouldn't Be Committed

```bash
# Remove virtual environment
rm -rf venv/

# Remove Python cache
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete

# Remove database files
rm -f instance/*.db
rm -f backend/instance/*.db
rm -f *.db

# Remove log files
rm -rf logs/
rm -rf backend/logs/
rm -f *.log

# Remove generated reports
rm -rf reports/

# Remove frontend build output
rm -rf frontend/dist/
rm -rf frontend/node_modules/

# Remove generated images
rm -f schedule_chart.png
rm -f backend/schedule_chart.png
rm -f reports/*.png
rm -f reports/*.jpg

# Remove service account credentials (keep .example)
# ⚠️ DO NOT DELETE service-account-creds.json if you need it locally
# Just ensure it's in .gitignore
```

### Step 4: Update .gitignore
```bash
# Replace .gitignore with improved version
cp .gitignore.IMPROVED .gitignore
```

---

## ✅ Verify Before Committing

### Step 5: Check What Will Be Committed
```bash
# See what files Git will track
git status

# See what files would be committed
git add -n .
git status

# Verify sensitive files are ignored
git check-ignore service-account-creds.json
git check-ignore .env
git check-ignore instance/*.db
git check-ignore venv/
```

### Step 6: Create Initial Commit
```bash
# Stage all files
git add .

# Verify one more time
git status

# Create initial commit
git commit -m "Initial commit: Smart Scheduling SaaS System

- Flask backend with multi-tenant support
- React frontend
- CP-SAT scheduling engine
- Docker containerization
- Google Sheets integration"
```

---

## 📋 Post-Commit Checklist

- [ ] Verify `.gitignore` is working (check `git status`)
- [ ] Verify no credentials in repository
- [ ] Create `README.md` at root with setup instructions
- [ ] Document required environment variables
- [ ] Add deployment instructions
- [ ] Consider adding CI/CD (GitHub Actions)
- [ ] Consider adding tests

---

## 🔐 Security Reminders

1. **Never commit:**
   - `service-account-creds.json` (real credentials)
   - `.env` files
   - Database files (`*.db`)
   - Log files
   - Any file with passwords or API keys

2. **Always use:**
   - Environment variables for secrets
   - `.env.example` for documentation
   - `.gitignore` to exclude sensitive files

3. **If credentials were committed:**
   - Rotate them immediately
   - Remove from Git history (see Step 1)
   - Notify team members

---

## 🎯 Quick Commands Reference

```bash
# Check for sensitive files
git log --all --full-history -- "*.json" | grep -i "credential\|secret\|key"

# Remove file from Git history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch FILENAME" \
  --prune-empty --tag-name-filter cat -- --all

# Verify .gitignore is working
git check-ignore -v FILENAME

# Clean untracked files
git clean -fd

# See what would be committed
git diff --cached
```

---

**Status:** Ready for GitHub after completing these steps ✅

