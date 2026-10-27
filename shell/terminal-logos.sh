# terminal-logos: pin a faint logo behind claude / devin / opencode / codex while they run.
# Source from ~/.zshrc or ~/.bashrc (install.sh adds the line for you).
#
#   TERMINAL_LOGOS_DIR      where the logos + logo-pty.py live
#                           (default: ${XDG_DATA_HOME:-~/.local/share}/terminal-logos)
#   TERMINAL_LOGOS_WEZTERM  set to 1 to try the CLI logos in WezTerm (experimental: it relies
#                           on kitty-graphics images drawn below the text)
#   TERMINAL_LOGOS_DISABLE  set to 1 to turn the wrappers off without editing your rc file

: "${TERMINAL_LOGOS_DIR:=${XDG_DATA_HOME:-$HOME/.local/share}/terminal-logos}"

_terminal_logos_supported() {
  [ -t 0 ] && [ -t 1 ] && [ "${TERMINAL_LOGOS_DISABLE:-0}" != 1 ] || return 1
  case "${TERM_PROGRAM:-}" in
    ghostty) return 0 ;;
    WezTerm) [ "${TERMINAL_LOGOS_WEZTERM:-0}" = 1 ] ;;
    *) return 1 ;;
  esac
}

# _terminal_logos_run NAME IMAGE_ID COMMAND [ARGS...]
_terminal_logos_run() {
  local name=$1 id=$2 img
  shift 2
  img="$TERMINAL_LOGOS_DIR/$name-logo-faint.png"
  if _terminal_logos_supported && [ -f "$img" ] && [ -f "$TERMINAL_LOGOS_DIR/logo-pty.py" ]; then
    python3 -I "$TERMINAL_LOGOS_DIR/logo-pty.py" "$img" "$id" "$@"
  else
    command "$@"
  fi
}

claude()   { _terminal_logos_run claude   7171 claude   "$@"; }
devin()    { _terminal_logos_run devin    7272 devin    "$@"; }
opencode() { _terminal_logos_run opencode 7373 opencode "$@"; }
codex()    { _terminal_logos_run codex    7474 codex    "$@"; }
