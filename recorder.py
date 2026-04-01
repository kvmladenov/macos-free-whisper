import numpy as np
import sounddevice as sd
from config import SAMPLE_RATE, CHANNELS


class Recorder:
    def __init__(self):
        self._buffer = []
        self._stream = None

    def _callback(self, indata, frames, time, status):
        self._buffer.append(indata.copy())

    def start(self):
        self._buffer = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._buffer:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(self._buffer, axis=0)
        # Flatten to 1D mono
        return audio.flatten()
