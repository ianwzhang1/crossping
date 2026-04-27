# CrossPing

CrossPing is a small desktop app for macOS and Windows that lets users hold
`Ctrl+Shift` and left-drag anywhere on screen to publish drawing strokes over
MQTT. Holding `Ctrl+Shift` and right-click clears only that sender's strokes
across peers in the same room.

## Features

- Global `Ctrl+Shift+left-drag` gesture publishes normalized stroke points.
- Global `Ctrl+Shift+right-click` clears the current sender's strokes locally
  and remotely.
- Transparent always-on-top overlay for local and remote rendering.
- Room-scoped MQTT topics with non-PII payloads. The default room publishes to
  `crossping/67`.
- Small settings window for room and broker configuration.

## Development

```bash
pipenv install --dev
pipenv run pip install -e .[desktop]
pipenv run python -m crossping
pipenv run pytest
```

## Packaging

PyInstaller is the intended packaging path for both macOS and Windows:

```bash
pyinstaller packaging/crossping.spec
```

## GitHub Actions

To build a Windows package from GitHub:

1. Push the repo to GitHub.
2. Open the `Actions` tab.
3. Run `Build Windows Package` manually, or push to `main`.
4. Download the `CrossPing-windows` artifact from the workflow run.

The workflow builds on a real Windows runner, runs the test suite, packages the
app with PyInstaller, and uploads a zip containing the Windows build.

macOS requires Accessibility/Input Monitoring permissions for global input
capture. Windows users may need to allow firewall access for outbound MQTT.

Set `CROSSPING_CONFIG_DIR` if you need CrossPing to store its config somewhere
other than the default per-platform app-data directory.
