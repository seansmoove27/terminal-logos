# terminal-logos

Faint dotted logos behind your terminal text:

- **Idle shells** show the Ghostty ghost, centered in every pane.
- **AI coding CLIs** (`claude`, `devin`, `opencode`, `codex`) get their own logo pinned behind their output while they run. Each logo sits on a solid backing that hides the ghost.

The logos are drawn as a halftone dot grid at low opacity, so text on top stays readable.

## Terminal support

| | Idle-pane ghost | CLI logos |
|---|---|---|
| [Ghostty](https://ghostty.org) | ✅ `background-image` | ✅ |
| [WezTerm](https://wezterm.org) | ✅ `config.background` (one per window, not per pane) | ⚠️ Experimental, opt in with `TERMINAL_LOGOS_WEZTERM=1` |
| Anything else | — | Wrappers step aside and run the CLI as normal |

The CLI logos use the [kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/) with a z-index below the text. WezTerm's support for that is incomplete, so it may not render correctly there. Reports are welcome.

## Install

Requires macOS or Linux, `python3` ≥ 3.9, and [uv](https://docs.astral.sh/uv/). uv runs the logo generator with its dependencies (Pillow, NumPy, PyMuPDF) without touching your global Python.

```sh
git clone https://github.com/seansmoove27/terminal-logos.git
cd terminal-logos
./install.sh
```

`install.sh` does three things:

1. Builds the PNGs into `${XDG_DATA_HOME:-~/.local/share}/terminal-logos`. On first run, it downloads the official Claude, Devin and Ghostty marks into `sources/` there.
2. Copies `logo-pty.py` and `shell/terminal-logos.sh` next to the PNGs.
3. Appends one `source` line to `~/.zshrc` and/or `~/.bashrc`. Pass `--no-rc` to skip this and add it yourself.

It never edits your terminal config. Add the idle-pane ghost yourself:

- **Ghostty:** add the lines from [`ghostty/config.snippet`](ghostty/config.snippet) to `~/.config/ghostty/config`. Use the full path; `install.sh` prints it.
- **WezTerm:** add [`wezterm/wezterm.lua.snippet`](wezterm/wezterm.lua.snippet) to your `wezterm.lua`.

Open a new shell and run `claude` (or `devin` / `opencode` / `codex`).

## Match your theme

The defaults are tuned for [Catppuccin Mocha](https://catppuccin.com). For any other theme, rebuild with your terminal's background and foreground colors:

```sh
./install.sh --bg '#282828' --fg '#ebdbb2'      # e.g. Gruvbox Dark
./install.sh --alpha 60                         # fainter dots (0-255, default 90)
```

`--bg` must match your terminal background exactly. Otherwise the solid backing behind each CLI logo shows up as a visible square. In WezTerm, also update the `Color` layer in the snippet.

## Configuration

| Variable | Effect |
|---|---|
| `TERMINAL_LOGOS_DIR` | Where the logos live (default `${XDG_DATA_HOME:-~/.local/share}/terminal-logos`) |
| `TERMINAL_LOGOS_WEZTERM=1` | Enable CLI logos in WezTerm |
| `TERMINAL_LOGOS_DISABLE=1` | Turn the wrappers off for this shell |

## How it works

- **`make-dotted-logos.py`** turns each logo into a mask, then renders it as a halftone. It checks every grid offset and picks the one with the fewest half-covered cells, so edges stay crisp. Each dot's size follows how much of its cell the logo covers. The script declares its dependencies inline ([PEP 723](https://peps.python.org/pep-0723/)), so `uv run make-dotted-logos.py --help` just works.
- **`logo-pty.py`** runs the CLI on its own pseudo-terminal and passes the output through. Ghostty drops image placements on every screen clear and alt-screen switch, and these CLIs clear and redraw constantly. So the script splices the logo placement into the same write as each clear, and the terminal never draws a frame without the logo. It uses only the standard library.
- **`shell/terminal-logos.sh`** defines `claude()`, `devin()`, etc. These functions call `logo-pty.py` only when stdin/stdout are a TTY in a supported terminal. Otherwise they run `command <cli>` unchanged, so pipes, scripts and other terminals behave exactly as before.

## Uninstall

```sh
rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/terminal-logos"
```

Then delete the line ending in `# terminal-logos` from `~/.zshrc` / `~/.bashrc`, and the `background-image` lines from your terminal config.

## Development

```sh
uvx ruff check . && uvx ruff format --check .
uvx --from shellcheck-py shellcheck install.sh shell/terminal-logos.sh
```

## Trademarks

This is an unofficial fan project. It isn't affiliated with or endorsed by Anthropic, Cognition, OpenAI, SST or the Ghostty project. Claude, Devin, Codex, opencode and Ghostty are trademarks of their owners.

To avoid redistributing those marks, this repo contains no logo images. The generator downloads them at install time from these sources:

- Claude: [Simple Icons](https://simpleicons.org)
- Devin: devin.ai
- Ghostty: the [ghostty-org/ghostty](https://github.com/ghostty-org/ghostty) repo

The opencode and codex shapes are drawn in code.

## License

[MIT](LICENSE) for the code in this repo. It does not cover the downloaded logos.
