import os
import sys
import numpy as np

from config import (
    SAMPLE_RATE,
    STT_ENGINE,
    WHISPER_MODEL_NAME,
    WHISPER_MODEL_DIR,
    ELEVENLABS_API_KEY,
    ELEVENLABS_API_URL,
    ELEVENLABS_MODEL_ID,
    ELEVENLABS_TIMEOUT,
)


# ── Custom exceptions ─────────────────────────────────────────────────
class TranscriptionError(Exception):
    """Base exception for all transcription failures."""


class NetworkError(TranscriptionError):
    """No internet or connection refused."""


class AuthError(TranscriptionError):
    """Invalid or missing API key (HTTP 401)."""


class RateLimitError(TranscriptionError):
    """Too many API requests (HTTP 429)."""


# ── Audio conversion utility ──────────────────────────────────────────
def float32_to_pcm_bytes(audio: np.ndarray) -> bytes:
    """Convert float32 1D numpy array to raw int16 PCM bytes.

    Args:
        audio: float32 numpy array, 1D, 16kHz mono, values in [-1.0, 1.0]

    Returns:
        Raw int16 little-endian PCM bytes (no WAV header)
    """
    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    return audio_int16.tobytes()


# ── Whisper engine (local) ────────────────────────────────────────────
class WhisperTranscriber:
    """Local speech-to-text using whisper.cpp via pywhispercpp."""

    def __init__(self):
        self._model = None

    def load_model(self):
        """Load the Whisper GGML model. Call once at startup (can be slow)."""
        from pywhispercpp.model import Model

        model_path = os.path.join(WHISPER_MODEL_DIR, f"ggml-{WHISPER_MODEL_NAME}.bin")
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Whisper model not found at {model_path}. Run setup.sh to download it."
            )
        sys.stderr.write(f"[mac-voice] Loading Whisper {WHISPER_MODEL_NAME} model...\n")
        self._model = Model(model_path, n_threads=os.cpu_count())
        sys.stderr.write("[mac-voice] Whisper model loaded.\n")

    def is_loaded(self) -> bool:
        return self._model is not None

    def transcribe(self, audio: np.ndarray, language: str = "auto") -> str:
        """Transcribe audio data to text.

        Args:
            audio: float32 numpy array, 1D, 16kHz mono
            language: "auto", "bg", or "en"

        Returns:
            Transcribed text string
        """
        if self._model is None:
            sys.stderr.write("[mac-voice] Whisper model not loaded, loading now...\n")
            self.load_model()

        if len(audio) == 0:
            sys.stderr.write("[mac-voice] Whisper: empty audio, skipping.\n")
            return ""

        lang = "" if language == "auto" else language
        params = {"translate": False, "print_progress": False, "language": lang}
        if language in ("auto", "bg"):
            params["initial_prompt"] = "Транскрипция на български език."

        sys.stderr.write(
            f"[mac-voice] Whisper transcribing {len(audio) / SAMPLE_RATE:.1f}s "
            f"audio (language={language})...\n"
        )
        segments = self._model.transcribe(audio, **params)
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
        sys.stderr.write(f"[mac-voice] Whisper result: {len(text)} chars.\n")
        return text


# ── ElevenLabs engine (cloud) ─────────────────────────────────────────
class ElevenLabsTranscriber:
    """Cloud speech-to-text using ElevenLabs Scribe v2 API.

    Supports automatic fallback to a local WhisperTranscriber if
    the API call fails and a fallback instance is provided.
    """

    def __init__(self, api_key: str, fallback: WhisperTranscriber = None):
        self._api_key = api_key
        self._fallback = fallback

    def load_model(self):
        """Validate API key and load fallback model if available.

        ElevenLabs has no local model to load, but we validate the API key
        with a lightweight request and pre-load the fallback Whisper model.
        """
        if not self._api_key:
            sys.stderr.write("[mac-voice] ELEVENLABS_API_KEY not set.\n")
            raise AuthError(
                "ELEVENLABS_API_KEY not set. Export it in your shell profile.\n"
                "Example: export ELEVENLABS_API_KEY='sk_...'"
            )

        sys.stderr.write("[mac-voice] Validating ElevenLabs API key...\n")
        try:
            import requests
            resp = requests.get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": self._api_key},
                timeout=10,
            )
            if resp.status_code == 401:
                raise AuthError(
                    "Invalid ElevenLabs API key. Check ELEVENLABS_API_KEY.\n"
                    "Visit: https://elevenlabs.io/app/settings/api-keys"
                )
            resp.raise_for_status()
            sys.stderr.write("[mac-voice] ElevenLabs API key valid.\n")
        except requests.exceptions.ConnectionError:
            # No internet — warn but don't block startup
            sys.stderr.write("[mac-voice] No internet for API key validation (OK, will validate on first use).\n")
        except AuthError:
            raise
        except Exception as e:
            sys.stderr.write(f"[mac-voice] API key validation warning: {e}\n")

        # Load fallback Whisper model if provided
        if self._fallback and not self._fallback.is_loaded():
            sys.stderr.write("[mac-voice] Pre-loading Whisper fallback model...\n")
            self._fallback.load_model()

    def is_loaded(self) -> bool:
        return bool(self._api_key)

    def transcribe(self, audio: np.ndarray, language: str = "auto") -> str:
        """Transcribe audio via ElevenLabs Scribe v2 API.

        Falls back to local Whisper automatically if the API call fails
        and a fallback instance is available.

        Args:
            audio: float32 numpy array, 1D, 16kHz mono
            language: "auto", "bg", or "en"

        Returns:
            Transcribed text string
        """
        if len(audio) == 0:
            sys.stderr.write("[mac-voice] ElevenLabs: empty audio, skipping.\n")
            return ""

        if not self._api_key:
            raise AuthError(
                "ELEVENLABS_API_KEY not set. Export it in your shell profile."
            )

        duration_sec = len(audio) / SAMPLE_RATE
        sys.stderr.write(
            f"[mac-voice] ElevenLabs transcribing {duration_sec:.1f}s audio "
            f"(language={language}, model={ELEVENLABS_MODEL_ID})...\n"
        )

        # ── Phase 1: Try ElevenLabs API ─────────────────────────────
        elevenlabs_error = None
        try:
            import requests

            pcm_bytes = float32_to_pcm_bytes(audio)
            sys.stderr.write(
                f"[mac-voice] ElevenLabs: sending {len(pcm_bytes)} bytes "
                f"(raw int16 PCM, 16kHz mono)...\n"
            )

            lang_code = None if language == "auto" else language
            resp = requests.post(
                ELEVENLABS_API_URL,
                headers={"xi-api-key": self._api_key},
                data={
                    "model_id": ELEVENLABS_MODEL_ID,
                    "file_format": "pcm_s16le_16",
                    "language_code": lang_code,
                    "tag_audio_events": False,
                    "no_verbatim": True,
                    "diarize": False,
                    "timestamps_granularity": "none",
                },
                files={
                    "file": ("audio.pcm", pcm_bytes, "application/octet-stream")
                },
                timeout=ELEVENLABS_TIMEOUT,
            )

            sys.stderr.write(
                f"[mac-voice] ElevenLabs response: HTTP {resp.status_code}\n"
            )

            if resp.status_code == 401:
                raise AuthError("Invalid ElevenLabs API key. Check ELEVENLABS_API_KEY.")
            elif resp.status_code == 429:
                retry = resp.headers.get("Retry-After", "a moment")
                raise RateLimitError(
                    f"ElevenLabs rate limited. Try again in {retry} seconds."
                )
            elif resp.status_code >= 500:
                raise NetworkError("ElevenLabs service unavailable. Try again shortly.")
            resp.raise_for_status()

            data = resp.json()
            text = data.get("text", "").strip()

            if not text:
                sys.stderr.write("[mac-voice] ElevenLabs: no speech detected in audio.\n")
                return ""

            sys.stderr.write(
                f"[mac-voice] ElevenLabs result: {len(text)} chars "
                f"(detected language: {data.get('language_code', '?')}, "
                f"confidence: {data.get('language_probability', '?')})\n"
            )
            return text

        except requests.exceptions.Timeout:
            elevenlabs_error = NetworkError(
                f"ElevenLabs request timed out after {ELEVENLABS_TIMEOUT}s."
            )
        except requests.exceptions.ConnectionError:
            elevenlabs_error = NetworkError(
                "No internet connection. Cannot reach ElevenLabs API."
            )
        except requests.exceptions.RequestException as e:
            elevenlabs_error = NetworkError(f"ElevenLabs network error: {e}")
        except (AuthError, RateLimitError, NetworkError, TranscriptionError) as e:
            elevenlabs_error = e
        except Exception as e:
            elevenlabs_error = TranscriptionError(f"ElevenLabs error: {e}")

        # ── Phase 2: Auto-fallback to Whisper ───────────────────────
        sys.stderr.write(
            f"[mac-voice] ElevenLabs failed: "
            f"{type(elevenlabs_error).__name__}: {elevenlabs_error}\n"
        )

        if self._fallback and self._fallback.is_loaded():
            sys.stderr.write("[mac-voice] Auto-fallback to local Whisper...\n")
            try:
                fallback_text = self._fallback.transcribe(audio, language)
                if fallback_text:
                    sys.stderr.write(
                        f"[mac-voice] Whisper fallback OK: {len(fallback_text)} chars.\n"
                    )
                return fallback_text
            except Exception as fb_exc:
                sys.stderr.write(
                    f"[mac-voice] Whisper fallback also failed: {fb_exc}\n"
                )
                raise TranscriptionError(
                    f"Both engines failed. ElevenLabs: {elevenlabs_error}. "
                    f"Whisper: {fb_exc}"
                ) from fb_exc

        # No fallback available — raise original error
        raise elevenlabs_error


# ── Factory ───────────────────────────────────────────────────────────
def create_transcriber(engine: str = None):
    """Create a transcriber instance for the given engine.

    Args:
        engine: "elevenlabs" or "whisper". Defaults to STT_ENGINE from config.

    Returns:
        A transcriber instance with .load_model() and .transcribe() methods.
    """
    if engine is None:
        engine = STT_ENGINE

    sys.stderr.write(f"[mac-voice] Creating transcriber: engine={engine}\n")

    if engine == "elevenlabs":
        # Try to create Whisper fallback
        fallback = None
        try:
            fallback = WhisperTranscriber()
            sys.stderr.write("[mac-voice] Whisper fallback instance created.\n")
        except Exception as e:
            sys.stderr.write(
                f"[mac-voice] Whisper fallback unavailable: {e}\n"
                "  ElevenLabs will run without local fallback.\n"
            )

        transcriber = ElevenLabsTranscriber(
            api_key=ELEVENLABS_API_KEY,
            fallback=fallback,
        )
        sys.stderr.write("[mac-voice] ElevenLabs transcriber ready.\n")
        return transcriber

    elif engine == "whisper":
        sys.stderr.write("[mac-voice] Whisper-only mode (no cloud).\n")
        return WhisperTranscriber()

    else:
        raise ValueError(
            f"Unknown STT engine: '{engine}'. "
            "Set MACVOICE_ENGINE to 'elevenlabs' or 'whisper'."
        )


# ── Backward-compatible alias ─────────────────────────────────────────
# The old code imported "Transcriber" — keep it pointing to the factory
# so existing imports don't break if someone hasn't updated yet.
# Actually: we always use create_transcriber() in new code.
# Keeping this for reference but it's unused.
Transcriber = WhisperTranscriber  # alias for backward compatibility
