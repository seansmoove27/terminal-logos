#!/usr/bin/env bash
# Build the dotted logos and install the shell wrappers.
#
#   ./install.sh [--no-rc] [make-dotted-logos.py options, e.g. --bg '#282828' --fg '#ebdbb2']
#
# Writes only to $TERMINAL_LOGOS_DIR (default ${XDG_DATA_HOME:-~/.local/share}/terminal-logos)
# and, unless --no-rc, appends one `source` line to ~/.zshrc and/or ~/.bashrc.
# Terminal configs are never edited: the Ghostty/WezTerm lines to paste are printed at the end.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
dest=${TERMINAL_LOGOS_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/terminal-logos}
edit_rc=1
gen_args=()
for arg in "$@"; do
  case $arg in
    --no-rc) edit_rc=0 ;;
    -h | --help)
      sed -n '2,8s/^# \{0,1\}//p' "$0"
      exit 0
      ;;
    *) gen_args+=("$arg") ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required to build the logos: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

mkdir -p "$dest"
uv run --quiet "$repo/make-dotted-logos.py" --out "$dest" ${gen_args[@]+"${gen_args[@]}"}
cp "$repo/logo-pty.py" "$repo/shell/terminal-logos.sh" "$dest/"

if [ "$edit_rc" = 1 ]; then
  line="[ -f \"$dest/terminal-logos.sh\" ] && . \"$dest/terminal-logos.sh\"  # terminal-logos"
  for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    [ -f "$rc" ] || continue
    if grep -qF '# terminal-logos' "$rc"; then
      echo "already sourced in $rc"
    else
      printf '\n%s\n' "$line" >>"$rc"
      echo "added source line to $rc"
    fi
  done
fi

cat <<EOF

Done. Open a new shell, then add the idle-pane ghost to your terminal:

  Ghostty (~/.config/ghostty/config):
    background-image = $dest/ghostty-logo-bg.png
    background-image-position = center
    background-image-fit = contain

  WezTerm: see $repo/wezterm/wezterm.lua.snippet
    (CLI logos in WezTerm are experimental: export TERMINAL_LOGOS_WEZTERM=1)
EOF
