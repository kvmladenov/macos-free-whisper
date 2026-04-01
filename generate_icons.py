"""Generate simple menubar icons for Mac Voice."""
from PIL import Image, ImageDraw
import os

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")
SIZE = 44  # 22pt @2x for retina


def create_icon(filename, color, shape="mic"):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if shape == "mic":
        # Microphone body (rounded rectangle)
        body_x = SIZE // 2
        draw.rounded_rectangle(
            [body_x - 6, 6, body_x + 6, 24],
            radius=6,
            fill=color,
        )
        # Microphone arc
        draw.arc([body_x - 10, 14, body_x + 10, 32], 0, 180, fill=color, width=2)
        # Stand
        draw.line([body_x, 32, body_x, 38], fill=color, width=2)
        draw.line([body_x - 6, 38, body_x + 6, 38], fill=color, width=2)

    elif shape == "dot":
        # Pulsing recording dot
        cx, cy = SIZE // 2, SIZE // 2
        draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=color)

    elif shape == "gear":
        # Processing indicator (circular arrows approximation)
        cx, cy = SIZE // 2, SIZE // 2
        draw.arc([cx - 10, cy - 10, cx + 10, cy + 10], 30, 330, fill=color, width=3)
        # Arrow head
        draw.polygon(
            [(cx + 8, cy - 12), (cx + 12, cy - 6), (cx + 4, cy - 6)],
            fill=color,
        )

    elif shape == "check":
        # Checkmark
        cx, cy = SIZE // 2, SIZE // 2
        draw.line(
            [(cx - 8, cy), (cx - 2, cy + 8), (cx + 10, cy - 8)],
            fill=color,
            width=3,
        )

    img.save(os.path.join(ICON_DIR, filename))


if __name__ == "__main__":
    os.makedirs(ICON_DIR, exist_ok=True)

    # Idle: gray microphone
    create_icon("idle.png", (120, 120, 120, 255), "mic")
    # Recording: red dot
    create_icon("recording.png", (220, 40, 40, 255), "dot")
    # Transcribing: orange processing
    create_icon("transcribing.png", (230, 160, 30, 255), "gear")
    # Done: green checkmark
    create_icon("done.png", (40, 200, 80, 255), "check")

    print("Icons generated in", ICON_DIR)
