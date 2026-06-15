$ErrorActionPreference = "Stop"

# Set Git Author Identity
git config user.name "reethj-07"
git config user.email "reethj-07@users.noreply.github.com"

# Get the first commit hash
$firstCommit = git rev-list --max-parents=0 HEAD

# Reset to first commit
git reset --soft $firstCommit
git restore --staged .

# 1. docs: add architecture design
git add DESIGN.md
git commit -m "docs: add architecture design"

# 2. chore: project scaffolding and configuration
git add .env.example .gitignore Dockerfile docker-compose.yml backend/pyproject.toml frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts
git commit -m "chore: project scaffolding and configuration"

# 3. feat: backend connector client and scanner logic
git add backend/app/__init__.py backend/app/connector/
git commit -m "feat: backend connector client and scanner logic"

# 4. feat: database persistence layer and schemas
git add backend/app/storage.py backend/app/schemas.py backend/app/config.py
git commit -m "feat: database persistence layer and schemas"

# 5. feat: fastapi routing and main application
git add backend/app/main.py backend/app/routes.py
git commit -m "feat: fastapi routing and main application"

# 6. test: add backend pytest suite and mock server
git add backend/tests/
git commit -m "test: add backend pytest suite and mock server"

# 7. feat: react frontend implementation
git add frontend/src/ frontend/index.html
git commit -m "feat: react frontend implementation"

# 8. docs: update readme with deployment and live demo
git add README.md
git commit -m "docs: update readme with deployment and live demo"

# Add any leftover files just in case
git add .
$status = git status --porcelain
if ($status) {
    git commit -m "chore: final adjustments and build artifacts"
}

# Force push
git push origin main -f
