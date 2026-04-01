import time
import AppKit
import Quartz


def _get_clipboard_contents():
    """Get current clipboard string contents."""
    pb = AppKit.NSPasteboard.generalPasteboard()
    return pb.stringForType_(AppKit.NSPasteboardTypeString)


def _set_clipboard_contents(text):
    """Set clipboard string contents."""
    pb = AppKit.NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, AppKit.NSPasteboardTypeString)


def _simulate_paste():
    """Simulate Cmd+V keypress using Quartz CGEvents."""
    # Key code for 'V' is 9
    v_keycode = 9

    # Key down with Cmd modifier
    event_down = Quartz.CGEventCreateKeyboardEvent(None, v_keycode, True)
    Quartz.CGEventSetFlags(event_down, Quartz.kCGEventFlagMaskCommand)

    # Key up
    event_up = Quartz.CGEventCreateKeyboardEvent(None, v_keycode, False)
    Quartz.CGEventSetFlags(event_up, Quartz.kCGEventFlagMaskCommand)

    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up)


def paste_text(text: str):
    """Paste text at cursor position, preserving clipboard contents."""
    # Save current clipboard
    original = _get_clipboard_contents()

    # Set our text
    _set_clipboard_contents(text)

    # Small delay to ensure clipboard is updated
    time.sleep(0.05)

    # Simulate paste
    _simulate_paste()

    # Wait for paste to complete, then restore
    time.sleep(0.15)

    # Restore original clipboard
    if original is not None:
        _set_clipboard_contents(original)
    else:
        AppKit.NSPasteboard.generalPasteboard().clearContents()
