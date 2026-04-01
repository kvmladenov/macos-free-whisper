import os

# Audio settings
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1  # Mono

# Whisper model
MODEL_NAME = "large-v3"
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

# Language options: "auto" lets whisper detect, "bg" forces Bulgarian, "en" forces English
DEFAULT_LANGUAGE = "bg"
SUPPORTED_LANGUAGES = {
    "auto": "Auto Detect",
    "bg": "Bulgarian",
    "en": "English",
}

# History
MAX_HISTORY = 10

# UI
APP_NAME = "Mac Voice"
