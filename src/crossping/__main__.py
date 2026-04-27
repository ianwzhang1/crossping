from __future__ import annotations

from .app import CrossPingApp


def main() -> int:
    return CrossPingApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
