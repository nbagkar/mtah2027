#!/usr/bin/env bash
# One-time, per clone: block data/submission commits before they happen.
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cat > "$root/.git/hooks/pre-commit" <<'EOF'
#!/usr/bin/env bash
exec "$(git rev-parse --show-toplevel)/scripts/check_no_data.sh" staged
EOF
chmod +x "$root/.git/hooks/pre-commit"
echo "pre-commit hook installed"
