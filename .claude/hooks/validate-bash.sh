#!/usr/bin/env bash
# PreToolUse hook on the Bash tool (wired in .claude/settings.json).
# Blocks a short list of destructive patterns specific to this repo's
# footguns; everything else passes through untouched.
set -euo pipefail

input="$(cat)"
command="$(python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" <<<"$input" 2>/dev/null || true)"

[ -z "$command" ] && exit 0

deny() {
  echo "BLOCKED by validate-bash.sh: $1" >&2
  exit 2
}

case "$command" in
  *"rm -rf /"*|*"rm -rf ~"*)
    deny "recursive delete of root or home directory" ;;
  *"docker compose down -v"*|*"docker-compose down -v"*)
    deny "drops the postgres/redis/mongo volumes (all local consent/audit data) — use 'make reset' if that's intended, or confirm with the user first" ;;
  *"git push --force"*|*"git push -f"*)
    deny "force-push — confirm with the user first, especially on main" ;;
  *"git reset --hard"*)
    deny "discards uncommitted work — confirm with the user first" ;;
  *"DROP DATABASE"*|*"drop database"*)
    deny "drops a database" ;;
  *"DELETE FROM audit_log"*|*"TRUNCATE"*"audit_log"*)
    deny "audit_log is append-only by design (DB rule blocks UPDATE/DELETE) — this tries to bypass that" ;;
esac

exit 0
