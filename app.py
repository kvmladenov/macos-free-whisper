#!/usr/bin/env python3
"""Mac Voice — Local dictation tool with floating status window."""

import os
import queue
import threading
import time as _time
import sys
import signal

import AppKit
import Quartz
import objc
from objc import super
from PyObjCTools import AppHelper
from pynput import keyboard

from config import (
    APP_NAME,
    DEFAULT_LANGUAGE,
    MAX_HISTORY,
    SUPPORTED_LANGUAGES,
)
from recorder import Recorder
from transcriber import Transcriber
from clipboard import paste_text

# ── Layout constants ─────────────────────────────────────────────────
WINDOW_WIDTH = 300
STATUS_HEIGHT = 50
ROW_HEIGHT = 32
HISTORY_PADDING = 8
CORNER_RADIUS = 12
MARGIN = 16
SEPARATOR_HEIGHT = 1

STATE_CONFIG = {
    "idle":         ("🎙  Ready (⌘⇧1)",       (0.95, 0.95, 0.95)),
    "loading":      ("⏳  Loading model...",    (0.75, 0.75, 0.75)),
    "recording":    ("🔴  Recording... (⌘⇧1)", (1.0, 0.70, 0.70)),
    "transcribing": ("⏳  Transcribing...",     (1.0, 0.90, 0.60)),
    "done":         ("✅  Done!",               (0.70, 1.0, 0.70)),
}

# ── PID management ───────────────────────────────────────────────────
PID_FILE = os.path.join(os.path.dirname(__file__), ".macvoice.pid")


def kill_old_process():
    """Kill any previous Mac Voice process."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            # Check if process is actually a python mac-voice process
            if old_pid != os.getpid():
                import subprocess
                result = subprocess.run(
                    ["ps", "-p", str(old_pid), "-o", "command="],
                    capture_output=True, text=True,
                )
                cmd = result.stdout.strip()
                if "app.py" in cmd and "mac-voice" in cmd:
                    os.kill(old_pid, signal.SIGTERM)
                    sys.stderr.write(f"Killed old Mac Voice process (PID {old_pid})\n")
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    # Write our PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def cleanup_pid():
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


# ── App Delegate ─────────────────────────────────────────────────────
class AppDelegate(AppKit.NSObject):

    def init(self):
        self = objc.super(AppDelegate, self).init()
        if self is None:
            return None
        self.state = "loading"
        self.language = DEFAULT_LANGUAGE
        self.history = []
        self.recorder = Recorder()
        self.transcriber = Transcriber()
        self.model_ready = False
        self.action_queue = queue.Queue()
        self.expanded = False
        self.panel = None
        self._record_start_time = None
        self._record_timer = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        self._create_window()
        self._set_state("loading")

        AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.15, self, b"processQueue:", None, True
        )

        self._start_hotkey_listener()
        threading.Thread(target=self._load_model, daemon=True).start()

    # ── Window ───────────────────────────────────────────────────────

    def _create_window(self):
        # Initial position — will be repositioned near cursor on first hotkey
        mouse_loc = AppKit.NSEvent.mouseLocation()
        target_screen = AppKit.NSScreen.mainScreen()
        for screen in AppKit.NSScreen.screens():
            if AppKit.NSPointInRect(mouse_loc, screen.frame()):
                target_screen = screen
                break
        vf = target_screen.visibleFrame()
        x = vf.origin.x + vf.size.width - WINDOW_WIDTH - MARGIN
        y = vf.origin.y + vf.size.height - STATUS_HEIGHT - MARGIN

        rect = AppKit.NSMakeRect(x, y, WINDOW_WIDTH, STATUS_HEIGHT)

        self.panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self.panel.setLevel_(AppKit.NSFloatingWindowLevel)
        self.panel.setOpaque_(False)
        self.panel.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.panel.setHasShadow_(True)
        self.panel.setMovableByWindowBackground_(True)
        self.panel.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
            | AppKit.NSWindowCollectionBehaviorStationary
        )
        self.panel.setHidesOnDeactivate_(False)

        # Root view
        self.root_view = AppKit.NSVisualEffectView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, STATUS_HEIGHT)
        )
        self.root_view.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        self.root_view.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        self.root_view.setState_(AppKit.NSVisualEffectStateActive)
        self.root_view.setWantsLayer_(True)
        self.root_view.layer().setCornerRadius_(CORNER_RADIUS)
        self.root_view.layer().setMasksToBounds_(True)
        self.panel.setContentView_(self.root_view)

        # ── Status bar area (always at the TOP of the view) ──
        self._add_status_bar()

        # ── History area (below status, hidden initially) ──
        self.history_container = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, 0)
        )
        self.history_container.setHidden_(True)
        self.root_view.addSubview_(self.history_container)

        self.panel.orderFrontRegardless()

    @objc.python_method
    def _add_status_bar(self):
        # Status label — positioned relative to top of root_view
        # We'll update y in _relayout
        self.status_label = AppKit.NSTextField.labelWithString_("Loading...")
        self.status_label.setFont_(
            AppKit.NSFont.systemFontOfSize_weight_(13, AppKit.NSFontWeightMedium)
        )
        self.status_label.setTextColor_(AppKit.NSColor.whiteColor())
        self.status_label.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
        self.root_view.addSubview_(self.status_label)

        # Expand button (▾)
        self.toggle_btn = self._make_button("▾", b"toggleExpand:", size=16)
        self.root_view.addSubview_(self.toggle_btn)

        # Close button (✕)
        self.close_btn = self._make_button("✕", b"closeClicked:", size=14)
        self.root_view.addSubview_(self.close_btn)

        self._relayout()

    @objc.python_method
    def _make_button(self, title, action, size=14):
        btn = AppKit.NSButton.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, 32, 32))
        btn.setBezelStyle_(AppKit.NSBezelStyleInline)
        btn.setBordered_(False)
        btn.setTitle_(title)
        btn.setFont_(AppKit.NSFont.systemFontOfSize_(size))
        btn.setContentTintColor_(
            AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(0.7, 0.7, 0.7, 1.0)
        )
        btn.setTarget_(self)
        btn.setAction_(action)
        return btn

    @objc.python_method
    def _relayout(self):
        """Reposition all elements based on current window height."""
        h = self.panel.frame().size.height
        top = h - STATUS_HEIGHT

        # Status label
        self.status_label.setFrame_(
            AppKit.NSMakeRect(14, top + 13, WINDOW_WIDTH - 90, 26)
        )
        # Buttons at top-right
        self.toggle_btn.setFrame_(
            AppKit.NSMakeRect(WINDOW_WIDTH - 68, top + 9, 32, 32)
        )
        self.close_btn.setFrame_(
            AppKit.NSMakeRect(WINDOW_WIDTH - 36, top + 9, 32, 32)
        )

    # ── Position near cursor ─────────────────────────────────────────

    @objc.python_method
    def _position_near_cursor(self):
        """Position window in top-right corner of the screen where the mouse cursor is."""
        mouse_loc = AppKit.NSEvent.mouseLocation()
        # Find which screen the cursor is on
        target_screen = AppKit.NSScreen.mainScreen()
        for screen in AppKit.NSScreen.screens():
            if AppKit.NSPointInRect(mouse_loc, screen.frame()):
                target_screen = screen
                break

        sf = target_screen.frame()
        vf = target_screen.visibleFrame()  # excludes menubar/dock
        x = vf.origin.x + vf.size.width - WINDOW_WIDTH - MARGIN
        y = vf.origin.y + vf.size.height - STATUS_HEIGHT - MARGIN
        self.panel.setFrameOrigin_(AppKit.NSMakePoint(x, y))

    # ── Recording timer ──────────────────────────────────────────────

    @objc.python_method
    def _start_record_timer(self):
        self._record_start_time = _time.time()
        self._record_timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, b"updateRecordTimer:", None, True
        )

    @objc.python_method
    def _stop_record_timer(self):
        if self._record_timer:
            self._record_timer.invalidate()
            self._record_timer = None
        self._record_start_time = None

    def updateRecordTimer_(self, timer):
        if self._record_start_time:
            elapsed = int(_time.time() - self._record_start_time)
            mins, secs = divmod(elapsed, 60)
            self.status_label.setStringValue_(f"🔴  Recording {mins}:{secs:02d} (⌘⇧1)")

    # ── State ────────────────────────────────────────────────────────

    @objc.python_method
    def _set_state(self, state):
        self.state = state
        text, text_clr = STATE_CONFIG.get(state, STATE_CONFIG["idle"])
        r, g, b = text_clr
        self.status_label.setStringValue_(text)
        self.status_label.setTextColor_(
            AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, 1.0)
        )

    # ── Resize ───────────────────────────────────────────────────────

    @objc.python_method
    def _resize_window(self, new_height):
        frame = self.panel.frame()
        dy = frame.size.height - new_height
        frame.origin.y += dy
        frame.size.height = new_height
        self.panel.setFrame_display_animate_(frame, True, True)
        self.root_view.setFrame_(AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, new_height))
        self._relayout()

    # ── History UI ───────────────────────────────────────────────────

    @objc.python_method
    def _rebuild_history(self):
        for sv in list(self.history_container.subviews()):
            sv.removeFromSuperview()

        if not self.history:
            self.history_container.setHidden_(True)
            if self.expanded:
                self.expanded = False
                self.toggle_btn.setTitle_("▾")
                self._resize_window(STATUS_HEIGHT)
            return

        total_h = len(self.history) * ROW_HEIGHT + HISTORY_PADDING
        self.history_container.setFrame_(
            AppKit.NSMakeRect(0, 0, WINDOW_WIDTH, total_h)
        )

        for i, text in enumerate(self.history):
            y = total_h - (i + 1) * ROW_HEIGHT
            display = text[:40] + "..." if len(text) > 40 else text

            # Separator line (except before first item)
            if i > 0:
                sep_y = y + ROW_HEIGHT - 1
                sep = AppKit.NSBox.alloc().initWithFrame_(
                    AppKit.NSMakeRect(14, sep_y, WINDOW_WIDTH - 28, SEPARATOR_HEIGHT)
                )
                sep.setBoxType_(AppKit.NSBoxSeparator)
                self.history_container.addSubview_(sep)

            btn = AppKit.NSButton.alloc().initWithFrame_(
                AppKit.NSMakeRect(10, y, WINDOW_WIDTH - 20, ROW_HEIGHT)
            )
            btn.setBezelStyle_(AppKit.NSBezelStyleInline)
            btn.setBordered_(False)
            btn.setTitle_(display)
            btn.setAlignment_(AppKit.NSTextAlignmentLeft)
            btn.setFont_(AppKit.NSFont.systemFontOfSize_(12))
            btn.setContentTintColor_(
                AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(0.8, 0.8, 0.8, 1.0)
            )
            btn.setTarget_(self)
            btn.setAction_(b"historyClicked:")
            btn.setTag_(i)
            self.history_container.addSubview_(btn)

        if self.expanded:
            new_h = STATUS_HEIGHT + total_h + HISTORY_PADDING
            self.history_container.setHidden_(False)
            self._resize_window(new_h)

    # ── Button actions ───────────────────────────────────────────────

    def closeClicked_(self, sender):
        self.panel.orderOut_(None)

    def toggleExpand_(self, sender):
        if not self.history:
            return

        self.expanded = not self.expanded
        if self.expanded:
            total_h = len(self.history) * ROW_HEIGHT + HISTORY_PADDING
            new_h = STATUS_HEIGHT + total_h + HISTORY_PADDING
            self.history_container.setHidden_(False)
            self._resize_window(new_h)
            self.toggle_btn.setTitle_("▴")
        else:
            self.history_container.setHidden_(True)
            self._resize_window(STATUS_HEIGHT)
            self.toggle_btn.setTitle_("▾")

    def historyClicked_(self, sender):
        idx = sender.tag()
        if 0 <= idx < len(self.history):
            text = self.history[idx]
            pb = AppKit.NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(text, AppKit.NSPasteboardTypeString)
            self.status_label.setStringValue_("📋  Copied!")
            threading.Timer(
                1.0, lambda: self.action_queue.put(("restore_state",))
            ).start()

    # ── Hotkey ───────────────────────────────────────────────────────

    @objc.python_method
    def _start_hotkey_listener(self):
        CMD_FLAG = 1048576
        SHIFT_FLAG = 131072

        def on_press(key):
            try:
                # Check if '1' key (vk=18) or '!' (shift+1)
                is_target = False
                if hasattr(key, 'vk') and key.vk == 18:
                    is_target = True
                elif hasattr(key, 'char') and key.char in ('1', '!'):
                    is_target = True

                if is_target:
                    flags = getattr(listener, '_flags', 0)
                    has_cmd = bool(flags & CMD_FLAG)
                    has_shift = bool(flags & SHIFT_FLAG)
                    if has_cmd and has_shift:
                        sys.stderr.write(f"[hotkey] ⌘⇧1 pressed, state={self.state}\n")
                        self.action_queue.put(("toggle",))
            except Exception as e:
                sys.stderr.write(f"[hotkey error] {e}\n")

        listener = keyboard.Listener(on_press=on_press)
        listener.daemon = True
        listener.start()
        self._listener = listener

    # ── Model ────────────────────────────────────────────────────────

    @objc.python_method
    def _load_model(self):
        try:
            self.transcriber.load_model()
            self.model_ready = True
            self.action_queue.put(("set_state", "idle"))
        except FileNotFoundError as e:
            self.action_queue.put(("flash", f"Error: {e}"))

    # ── Recording ────────────────────────────────────────────────────

    @objc.python_method
    def _toggle_recording(self):
        sys.stderr.write(f"[toggle] state={self.state}, model_ready={self.model_ready}\n")

        if not self.panel.isVisible():
            self._position_near_cursor()
            self.panel.orderFrontRegardless()

        if self.state == "idle":
            if not self.model_ready:
                sys.stderr.write("[toggle] model not ready, ignoring\n")
                return
            self._position_near_cursor()
            self._set_state("recording")
            self._start_record_timer()
            self.recorder.start()
            sys.stderr.write("[toggle] recording started\n")

        elif self.state == "recording":
            self._stop_record_timer()
            self._set_state("transcribing")
            audio = self.recorder.stop()
            sys.stderr.write(f"[toggle] recording stopped, audio length={len(audio)}\n")
            threading.Thread(
                target=self._do_transcribe, args=(audio,), daemon=True
            ).start()

    @objc.python_method
    def _do_transcribe(self, audio):
        try:
            text = self.transcriber.transcribe(audio, language=self.language)
            if text:
                self.action_queue.put(("paste", text))
                self.action_queue.put(("add_history", text))
        except Exception as e:
            self.action_queue.put(("flash", f"Error: {e}"))
        self.action_queue.put(("done_then_idle",))

    # ── Queue (main thread) ──────────────────────────────────────────

    def processQueue_(self, timer):
        while not self.action_queue.empty():
            try:
                action = self.action_queue.get_nowait()
            except queue.Empty:
                break

            cmd = action[0]

            if cmd == "toggle":
                self._toggle_recording()
            elif cmd == "set_state":
                self._set_state(action[1])
            elif cmd == "restore_state":
                self._set_state(self.state)
            elif cmd == "paste":
                paste_text(action[1])
            elif cmd == "add_history":
                self.history.insert(0, action[1])
                self.history = self.history[:MAX_HISTORY]
                self._rebuild_history()
            elif cmd == "flash":
                self.status_label.setStringValue_(action[1])
            elif cmd == "done_then_idle":
                self._set_state("done")
                threading.Timer(
                    1.5, lambda: self.action_queue.put(("set_state", "idle"))
                ).start()


# ── Main ─────────────────────────────────────────────────────────────
def main():
    kill_old_process()
    import atexit
    atexit.register(cleanup_pid)

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)

    # Handle Ctrl+C gracefully
    import signal
    def sigint_handler(sig, frame):
        sys.stderr.write("\nQuitting Mac Voice...\n")
        cleanup_pid()
        AppHelper.stopEventLoop()
        sys.exit(0)
    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigint_handler)

    sys.stderr.write("Mac Voice started. Press ⌘⇧1 to record. Ctrl+C to quit.\n")
    AppHelper.runEventLoop(installInterrupt=True)


if __name__ == "__main__":
    main()
