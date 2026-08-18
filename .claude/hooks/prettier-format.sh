#!/bin/bash

# Post-tool-use hook for Claude Code
# Formats frontend files with Prettier after Claude writes or edits them.
#
# Scope: only files under client/, and only extensions Prettier handles here.
# Prettier is a devDependency of client/package.json, so it must run from that
# directory - running from the repo root finds no local prettier binary.

INPUT=$(cat)

# Edit reports the path under tool_input; Write's response carries filePath.
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[ -z "$FILE" ] && exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
CLIENT_DIR="${PROJECT_DIR}/client"

# Only format inside client/. Backend Python and server JSON data are out of scope.
case "$FILE" in
    "${CLIENT_DIR}"/*) ;;
    *) exit 0 ;;
esac

# Guard by extension rather than relying on --ignore-unknown, so the list of
# formatted types stays explicit and reviewable.
case "$FILE" in
    *.js|*.jsx|*.ts|*.tsx|*.vue|*.json|*.css|*.scss|*.html|*.md) ;;
    *) exit 0 ;;
esac

[ -f "$FILE" ] || exit 0

# Never block the tool: a formatting failure must not fail Claude's edit.
(cd "$CLIENT_DIR" && npx --no-install prettier --write "$FILE" >/dev/null 2>&1) || true

exit 0
