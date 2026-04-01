import os
import numpy as np
from pywhispercpp.model import Model
from config import MODEL_NAME, MODEL_DIR


class Transcriber:
    def __init__(self):
        self._model = None

    def load_model(self):
        """Load the whisper model. Call once at startup."""
        model_path = os.path.join(MODEL_DIR, f"ggml-{MODEL_NAME}.bin")
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found at {model_path}. Run setup.sh to download it."
            )
        self._model = Model(model_path, n_threads=os.cpu_count())

    def transcribe(self, audio: np.ndarray, language: str = "auto") -> str:
        """Transcribe audio data to text.

        Args:
            audio: float32 numpy array, 16kHz mono
            language: "auto", "bg", or "en"
        """
        if self._model is None:
            self.load_model()

        if len(audio) == 0:
            return ""

        lang = "" if language == "auto" else language
        params = {"translate": False, "print_progress": False, "language": lang}
        if language in ("auto", "bg"):
            params["initial_prompt"] = "Транскрипция на български език."

        segments = self._model.transcribe(audio, **params)
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
        return text
