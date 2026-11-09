"""Device microphone capture utilities."""

import io
from collections.abc import Callable


def record_microphone(
    sample_rate: int = 16000,
    input_func: Callable[[str], str] = input,
    stream_factory=None,
) -> bytes:
    """Record until Enter is pressed and return 16-bit PCM WAV bytes."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be greater than zero")

    if stream_factory is None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Microphone recording requires sounddevice and scipy. "
                "Install the backend requirements first."
            ) from exc

    frames = []

    def callback(indata, frame_count, time_info, status):
        if status:
            print(f"[Microphone] {status}")
        frames.append(indata.copy())

    stream = (
        stream_factory(
            callback=callback,
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        if stream_factory
        else sd.InputStream(
            callback=callback,
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
    )
    started = False
    try:
        stream.start()
        started = True
        print("Recording started.")
        print("Speak naturally.")
        input_func("Press [Enter] to stop recording...")
    finally:
        if started:
            stream.stop()
        stream.close()

    if not frames:
        raise RuntimeError("No audio was captured from the microphone")

    try:
        import numpy as np
        from scipy.io.wavfile import write
    except ImportError as exc:
        raise RuntimeError(
            "Microphone recording requires sounddevice and scipy. "
            "Install the backend requirements first."
        ) from exc

    recording = np.concatenate(frames, axis=0)
    buffer = io.BytesIO()
    write(buffer, sample_rate, recording)
    return buffer.getvalue()
