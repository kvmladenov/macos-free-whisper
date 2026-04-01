# Mac Voice

Local speech-to-text dictation tool for macOS. Uses [whisper.cpp](https://github.com/ggerganov/whisper.cpp) (large-v3 model) running entirely on your Mac — no cloud services, no API keys, completely private.

Works great with **Bulgarian** and **English**. Optimized for Apple Silicon (M1/M2/M3/M4).

## How it works

1. Press **Cmd+Shift+1** — a small floating window appears, recording starts
2. Dictate your text
3. Press **Cmd+Shift+1** again — transcription runs locally on your GPU
4. Text is automatically pasted at your cursor position

The floating window shows recording time, transcription status, and keeps a history of your last 10 dictations.

## Requirements

- macOS (Apple Silicon recommended, Intel also works)
- Python 3.10+
- ~4GB free disk space (for the Whisper model)
- ~4GB RAM available (model loads into memory)

## Install

```bash
git clone https://github.com/YOUR_USERNAME/mac-voice.git
cd mac-voice
./setup.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Download the Whisper large-v3 model (~3GB)
- Add a `voice` command alias to your shell

## Usage

```bash
voice
```

- **Cmd+Shift+1** — Start/stop recording (toggle)
- **Ctrl+C** — Quit the app
- Click **▾** in the floating window to see transcription history
- Click any history item to copy it to clipboard
- Click **✕** to hide the window (hotkey still works to bring it back)

## macOS Permissions

On first run, macOS will ask for permissions. You need to grant:

1. **Microphone** — prompted automatically
2. **Accessibility** — needed for the global hotkey and text pasting
3. **Input Monitoring** — needed for keyboard shortcut detection

Go to **System Settings → Privacy & Security** and add your Terminal app (Terminal.app, iTerm2, Warp, etc.) to both **Accessibility** and **Input Monitoring**.

## Language

Default language is Bulgarian. The app also handles English words mixed into Bulgarian speech well.

To change the default language, edit `config.py`:
```python
DEFAULT_LANGUAGE = "bg"  # Options: "bg", "en", "auto"
```

## Troubleshooting

**Hotkey doesn't work?**
- Make sure your Terminal app is added to Accessibility AND Input Monitoring in System Settings

**Text not pasting?**
- Make sure your Terminal app is in the Accessibility list

**Model loading is slow?**
- First load takes ~5 seconds. Subsequent recordings are fast. The model stays in memory.

**Wrong language detected?**
- Set `DEFAULT_LANGUAGE = "bg"` or `"en"` in `config.py` instead of `"auto"`

## Tech Stack

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) via [pywhispercpp](https://github.com/absadiki/pywhispercpp) — speech recognition (Metal GPU accelerated)
- [PyObjC](https://pyobjc.readthedocs.io/) — native macOS floating window (NSPanel + NSVisualEffectView)
- [pynput](https://pynput.readthedocs.io/) — global keyboard shortcut
- [sounddevice](https://python-sounddevice.readthedocs.io/) — audio recording
- [NumPy](https://numpy.org/) — audio buffer handling

## License

MIT
