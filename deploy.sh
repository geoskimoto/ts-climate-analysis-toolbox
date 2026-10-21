#!/usr/bin/env bash
# Redeploy the PNW Climate Trends Explorer (FastAPI + Vite/React frontend).
#
#   ./deploy.sh                 test, then deploy BRANCH (default: main)
#   BRANCH=feat/baseflow ./deploy.sh
#   ./deploy.sh --skip-tests    skip the local test gate (not recommended)
#   ./deploy.sh --dry-run       print what would happen, change nothing
#
# Runs as your normal user; every step that touches the live app copy uses
# `sudo -u $SITE_USER` so files stay owned by the site user (never root).
# NOTE: written against the layout visible in climate-trends.service. Verify
# the paths below on first use with --dry-run.

set -euo pipefail

BRANCH="${BRANCH:-main}"
SERVICE="${SERVICE:-climate-trends.service}"
SITE_USER="${SITE_USER:-climtrends}"
APP_DIR="${APP_DIR:-/home/climtrends/htdocs/climate-trends.streamflows.org/app}"
VENV="${VENV:-$APP_DIR/.venv}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8055}"
REMOTE="${REMOTE:-origin}"

SKIP_TESTS=0
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --skip-tests) SKIP_TESTS=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
as_site() { sudo -u "$SITE_USER" "$@"; }
step() { printf '\n==> %s\n' "$*"; }
run() { if [ "$DRY_RUN" = 1 ]; then printf '[dry-run] %s\n' "$*"; else "$@"; fi; }
die() { echo "ERROR: $*" >&2; exit 1; }

# 1. Gate on the local checkout: it must be pushed, clean and green. -------------
step "Checking local checkout ($SRC_DIR)"
cd "$SRC_DIR"
[ -z "$(git status --porcelain)" ] || die "Working tree has uncommitted changes; commit or stash first."
git fetch --quiet "$REMOTE" "$BRANCH" || die "Cannot fetch $REMOTE/$BRANCH."
LOCAL_SHA="$(git rev-parse "$BRANCH" 2>/dev/null)" || die "Local branch $BRANCH does not exist."
REMOTE_SHA="$(git rev-parse "$REMOTE/$BRANCH")"
[ "$LOCAL_SHA" = "$REMOTE_SHA" ] || die "$BRANCH is not in sync with $REMOTE/$BRANCH (push or pull first); the live copy deploys what is on $REMOTE."

if [ "$SKIP_TESTS" = 0 ]; then
  step "Running tests (offline suite)"
  PY="$SRC_DIR/.venv/bin/python"; [ -x "$PY" ] || PY=python3
  "$PY" -m pytest tests -q -p no:cacheprovider -m "not network"
  (cd frontend && npm test --silent)
else
  echo "Skipping tests (--skip-tests)."
fi

# 2. Preflight on the live copy. --------------------------------------------------
step "Preflight on $APP_DIR (as $SITE_USER)"
as_site test -d "$APP_DIR/.git" || die "$APP_DIR is not a git clone readable by $SITE_USER; adjust APP_DIR or set it up first."
as_site test -x "$VENV/bin/python" || die "No virtualenv at $VENV."
as_site command -v npm >/dev/null || die "npm is not available to $SITE_USER; the frontend cannot be built there."
OLD_SHA="$(as_site git -C "$APP_DIR" rev-parse HEAD)"
echo "Currently deployed: $OLD_SHA"
echo "Deploying:          $REMOTE_SHA ($BRANCH)"

# 3. Update code (fast-forward only: never rewrites the live copy's history). -----
step "Updating code"
run as_site git -C "$APP_DIR" fetch --quiet "$REMOTE" "$BRANCH"
run as_site git -C "$APP_DIR" checkout --quiet "$BRANCH"
run as_site git -C "$APP_DIR" merge --ff-only "$REMOTE/$BRANCH"

# 4. Python deps only if pyproject.toml changed. ----------------------------------
if [ "$DRY_RUN" = 0 ] && as_site git -C "$APP_DIR" diff --quiet "$OLD_SHA" HEAD -- pyproject.toml; then
  echo "pyproject.toml unchanged; skipping pip install."
else
  step "Installing Python dependencies"
  run as_site "$VENV/bin/pip" install --quiet -e "$APP_DIR[api]"
fi

# 5. Build the frontend from the lockfile. ----------------------------------------
step "Building frontend"
run as_site bash -c "cd '$APP_DIR/frontend' && npm ci --silent && npm run build --silent"

# 6. Restart and verify. ----------------------------------------------------------
step "Restarting $SERVICE"
run sudo systemctl restart "$SERVICE"

step "Verifying"
if [ "$DRY_RUN" = 1 ]; then
  echo "[dry-run] would check $HEALTH_URL/api/health and /api/defaults"
  exit 0
fi
ok=0
for _ in $(seq 1 15); do
  if curl -fsS "$HEALTH_URL/api/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 2
done
if [ "$ok" = 0 ]; then
  echo "Health check failed. Recent logs:" >&2
  sudo journalctl -u "$SERVICE" -n 30 --no-pager >&2 || true
  echo "Roll back with:" >&2
  echo "  sudo -u $SITE_USER git -C $APP_DIR checkout --detach $OLD_SHA && (cd $APP_DIR/frontend && sudo -u $SITE_USER npm ci && sudo -u $SITE_USER npm run build) && sudo systemctl restart $SERVICE" >&2
  exit 1
fi
# /api/defaults is behind the portal login when JWT_SECRET is set, so 401 is also healthy.
code="$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL/api/defaults" || true)"
case "$code" in
  200|401) echo "OK: /api/health up, /api/defaults -> HTTP $code" ;;
  *) die "/api/defaults returned HTTP $code (expected 200 or 401). Check: sudo journalctl -u $SERVICE" ;;
esac
echo "Deployed $REMOTE_SHA ($BRANCH). Previous: $OLD_SHA"
