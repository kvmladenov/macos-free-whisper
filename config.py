import os


def _load_dotenv(dotenv_path=None):
    """Load key=value pairs from a .env file into os.environ.

    Only sets variables that are NOT already in the environment
    (existing env vars take precedence over .env file).
    """
    if dotenv_path is None:
        dotenv_path = os.path.join(os.path.dirname(__file__), ".env")

    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


# Load .env before reading any config values
_load_dotenv()


# ── Audio (shared by all engines) ────────────────────────────────────
SAMPLE_RATE = 16000  # 16kHz required by Whisper and ElevenLabs PCM format
CHANNELS = 1  # Mono

# ── Engine selection ─────────────────────────────────────────────────
# Environment variable: MACVOICE_ENGINE = "elevenlabs" | "whisper"
# Default: elevenlabs (Scribe v2 cloud API)
STT_ENGINE = os.environ.get("MACVOICE_ENGINE", "elevenlabs")

# ── ElevenLabs Scribe v2 (cloud) ─────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_API_URL = os.environ.get(
    "ELEVENLABS_API_URL",
    "https://api.elevenlabs.io/v1/speech-to-text"
)
ELEVENLABS_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "scribe_v2")
ELEVENLABS_TIMEOUT = int(os.environ.get("ELEVENLABS_TIMEOUT", "30"))

# ── Whisper (local) ──────────────────────────────────────────────────
WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL_NAME", "large-v3")
WHISPER_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

# ── Language (shared) ────────────────────────────────────────────────
# "auto" lets the engine detect, "bg" forces Bulgarian, "en" forces English
DEFAULT_LANGUAGE = os.environ.get("MACVOICE_LANG", "bg")
SUPPORTED_LANGUAGES = {
    "auto": "Auto Detect",
    "bg": "Bulgarian",
    "en": "English",
}

# ── History ──────────────────────────────────────────────────────────
MAX_HISTORY = 10

# ── UI ───────────────────────────────────────────────────────────────
APP_NAME = "Mac Voice"
