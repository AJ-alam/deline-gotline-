set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
PYTHON="$BACKEND/venv/Scripts/python.exe"
[ -x "$PYTHON" ] || PYTHON="$BACKEND/venv/bin/python"
PG_DUMP="${PG_DUMP:-/c/Program Files/PostgreSQL/18/bin/pg_dump.exe}"

CONFIRM=0
if [ "${1:-}" = "--confirm" ]; then CONFIRM=1; fi

# ── 1. Refuse to run against anything but the real Postgres ────────────────
# `|| true`: no match must fall through to the error message below, not trip
# `set -o pipefail` and exit silently.
DB_URL="$(grep -E '^DATABASE_URL=' "$BACKEND/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)"
if [ -z "$DB_URL" ]; then
  echo "ERROR: DATABASE_URL is not set in backend/.env — refusing to run."
  echo "       Without it Django silently falls back to local SQLite and this"
  echo "       script would wipe the wrong database."
  exit 1
fi
case "$DB_URL" in
  postgres*) ;;
  *) echo "ERROR: DATABASE_URL is not a postgres:// URL — refusing to run."; exit 1 ;;
esac

HOST="$(printf '%s' "$DB_URL" | sed -E 's|.*@([^:/]+).*|\1|')"
echo "Target database host: $HOST"
echo ""

# ── 2. Back up before deleting anything ────────────────────────────────────
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$REPO_ROOT/backups"
mkdir -p "$BACKUP_DIR"
DUMP="$BACKUP_DIR/supabase-$STAMP.dump"

if [ -x "$PG_DUMP" ]; then
  echo "Backing up to $DUMP ..."
  "$PG_DUMP" --format=custom --no-owner --no-privileges --file="$DUMP" "$DB_URL"
else
  echo "pg_dump not found at: $PG_DUMP"
  echo "Set PG_DUMP=/path/to/pg_dump.exe and re-run."
  exit 1
fi

if [ ! -s "$DUMP" ]; then
  echo "ERROR: backup file is empty — refusing to delete anything."
  exit 1
fi
echo "Backup written: $(du -h "$DUMP" | cut -f1)"
echo ""

# A JSON fixture alongside the dump: restorable with `manage.py loaddata` on any
# database, which the custom-format dump is not.
FIXTURE="$BACKUP_DIR/supabase-$STAMP.json"
echo "Writing Django fixture to $FIXTURE ..."
(cd "$BACKEND" && "$PYTHON" manage.py dumpdata \
  --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission \
  --exclude admin.logentry --indent 2 --output "$FIXTURE")
echo ""

# ── 3. Apply any migrations the deployed schema is missing ─────────────────
echo "Pending migrations:"
(cd "$BACKEND" && "$PYTHON" manage.py showmigrations --plan | grep -F '[ ]' || echo "  (none)")
echo ""

if [ "$CONFIRM" -ne 1 ]; then
  echo "Dry run complete. Backup taken, nothing deleted."
  echo "Re-run with --confirm to apply migrations and wipe the data."
  exit 0
fi

(cd "$BACKEND" && "$PYTHON" manage.py migrate)
echo ""

# ── 4. Wipe ────────────────────────────────────────────────────────────────
(cd "$BACKEND" && "$PYTHON" manage.py clean_db --confirm)
echo ""

# ── 5. Report what is left ─────────────────────────────────────────────────
(cd "$BACKEND" && "$PYTHON" manage.py shell -c "
from django.contrib.auth import get_user_model
from forms.models import Form, FormSubmission
from api.models import Application, Payment, PolicySetting, Profile
User = get_user_model()
print('Remaining rows')
print('  users            ', User.objects.count())
print('  profiles         ', Profile.objects.count())
print('  submissions      ', FormSubmission.objects.count())
print('  applications     ', Application.objects.count())
print('  payments         ', Payment.objects.count())
print('  forms (kept)     ', Form.objects.count())
print('  policies (kept)  ', PolicySetting.objects.count())
")

echo ""
echo "Reset complete. No accounts exist — create staff with:"
echo "  cd backend && ./venv/Scripts/python.exe manage.py create_staff --email <you>@deline.ca --name \"<Name>\" --role admin"
