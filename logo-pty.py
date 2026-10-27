"""Run a CLI (claude/devin/opencode/codex) with a faint logo pinned behind its text.

Usage: logo-pty.py IMAGE IMAGE_ID COMMAND [ARGS...]

Uses the kitty graphics protocol: z below -1073741824 draws below text and cell backgrounds
but above the terminal's background-image. IMAGE's directory must also hold logo-backing.png
(written by make-dotted-logos.py), a solid square that hides the background ghost around it.

Ghostty deletes kitty-graphics placements on a full screen clear (CSI 2J) and on alt-screen
switches, and the CLIs clear+redraw on focus changes and resizes. A separate process that
re-places the logo on a timer always leaves a frame or two where the background ghost
shows through. So instead this runs the CLI on its own pty, passes its output through, and
splices the logo placement in right after every clear, in the same write, so the terminal never
renders a frame without it. The logo is removed when the CLI exits.

Standard library only, so it runs on any python3 >= 3.9 without a virtualenv.
"""

from __future__ import annotations

import base64
import contextlib
import fcntl
import os
import re
import select
import signal
import struct
import sys
import termios
import tty
from pathlib import Path

SCALE = 0.35  # logo height as a fraction of the pane's shorter side; must match make-dotted-logos.py
# Output that wipes placements: ED2, ED22, RIS, and entering the alternate screen.
TRIGGERS = (b"\x1b[2J", b"\x1b[22J", b"\x1bc", b"\x1b[?1049h", b"\x1b[?1047h", b"\x1b[?47h")
TRIGGER = re.compile(b"|".join(re.escape(t) for t in TRIGGERS))
MAX_TRIGGER = max(map(len, TRIGGERS))  # so a trigger split across reads isn't missed


def winsize(fd: int) -> bytes:
    return fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8)


def place_seq(img: Path, backing: Path, img_id: int) -> bytes:
    rows, cols, xpix, ypix = struct.unpack("HHHH", winsize(sys.stdout.fileno()))
    if not (rows and cols and xpix and ypix):
        return b""
    cw, ch = xpix / cols, ypix / rows
    side = SCALE * min(xpix, ypix)
    r, c = max(1, round(side / ch)), max(1, round(side / cw))
    row, col = (rows - r) // 2 + 1, (cols - c) // 2 + 1
    path = base64.b64encode(bytes(img)).decode()
    back = base64.b64encode(bytes(backing)).decode()
    bid = img_id + 1
    # Backing: one extra row/two extra columns each side, so cell rounding can't let the ghost peek out.
    br, bc = max(1, row - 1), max(1, col - 2)
    # Save cursor, place backing then logo (fixed p=1 so re-placing replaces), restore cursor.
    return (
        f"\0337"
        f"\033[{br};{bc}H\033_Ga=T,f=100,t=f,i={bid},p=1,c={c + 4},r={r + 2},z=-1073741826,C=1,q=2;{back}\033\\"
        f"\033[{row};{col}H\033_Ga=T,f=100,t=f,i={img_id},p=1,c={c},r={r},z=-1073741825,C=1,q=2;{path}\033\\\0338"
    ).encode()


def clear_seq(img_id: int) -> bytes:
    return f"\033_Ga=d,d=I,i={img_id},q=2\033\\\033_Ga=d,d=I,i={img_id + 1},q=2\033\\".encode()


def split_held(rest: bytes) -> tuple[bytes, bytes]:
    """Hold back a trailing partial ESC sequence that could still become a trigger."""
    esc = rest.rfind(b"\x1b", max(0, len(rest) - MAX_TRIGGER))
    if esc != -1 and not TRIGGER.search(rest[esc:]) and b"\x1b" not in rest[esc + 1 :]:
        tail = rest[esc:]
        if any(t.startswith(tail) for t in TRIGGERS):
            return rest[:esc], tail
    return rest, b""


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    img, argv = Path(sys.argv[1]).expanduser().resolve(), sys.argv[3:]
    img_id = int(sys.argv[2])
    backing = img.with_name("logo-backing.png")
    stdin, stdout = sys.stdin.fileno(), sys.stdout.fileno()
    attrs = termios.tcgetattr(stdin)
    size = winsize(stdin)

    pid, master = os.forkpty()
    if pid == 0:
        termios.tcsetattr(0, termios.TCSANOW, attrs)
        fcntl.ioctl(0, termios.TIOCSWINSZ, size)
        try:
            os.execvp(argv[0], argv)
        finally:
            os._exit(127)

    def on_winch(*_: object) -> None:
        with contextlib.suppress(OSError):
            fcntl.ioctl(master, termios.TIOCSWINSZ, winsize(stdin))

    signal.signal(signal.SIGWINCH, on_winch)
    tty.setraw(stdin)
    held = b""  # tail that might be the start of a trigger split across reads
    try:
        while True:
            try:
                ready, _, _ = select.select([master, stdin], [], [])
            except InterruptedError:
                continue
            if stdin in ready:
                data = os.read(stdin, 65536)
                if not data:
                    break
                os.write(master, data)
            if master in ready:
                try:
                    data = os.read(master, 65536)
                except OSError:  # EIO once the child closes the pty
                    data = b""
                if not data:
                    break
                data, held = held + data, b""
                out, last = [], 0
                for m in TRIGGER.finditer(data):
                    out += [data[last : m.end()], place_seq(img, backing, img_id)]
                    last = m.end()
                rest, held = split_held(data[last:])
                out.append(rest)
                os.write(stdout, b"".join(out))
    finally:
        termios.tcsetattr(stdin, termios.TCSAFLUSH, attrs)
        os.write(stdout, held + clear_seq(img_id))
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    sys.exit(main())
