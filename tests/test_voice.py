from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from backend.voice.microphone import record_microphone
from backend.voice.voice_agent import VoiceSessionResult, run_voice_session


def test_microphone_capture_returns_wav_bytes():
    class FakeStream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]
            self.stopped = False
            self.closed = False

        def start(self):
            self.callback(Mock(copy=Mock(return_value="audio-frame")), 1, None, None)

        def stop(self):
            self.stopped = True

        def close(self):
            self.closed = True

    wavfile = ModuleType("scipy.io.wavfile")
    wavfile.write = Mock(side_effect=lambda buffer, rate, recording: buffer.write(b"RIFF"))
    scipy_io = ModuleType("scipy.io")
    scipy_io.wavfile = wavfile
    scipy = ModuleType("scipy")
    scipy.io = scipy_io
    numpy = ModuleType("numpy")
    numpy.concatenate = Mock(return_value="recording")
    sounddevice = ModuleType("sounddevice")
    sounddevice.InputStream = FakeStream

    with patch.dict(
        "sys.modules",
        {
            "sounddevice": sounddevice,
            "numpy": numpy,
            "scipy": scipy,
            "scipy.io": scipy_io,
            "scipy.io.wavfile": wavfile,
        },
    ):
        result = record_microphone(input_func=Mock(return_value=""))

    assert result == b"RIFF"
    wavfile.write.assert_called_once()


def test_voice_session_connects_microphone_prisma_and_agent():
    recorder = Mock(return_value=b"wav-audio")
    agent = Mock()
    agent_response = Mock()
    agent_response.response_text = "agent-response"
    agent.run.return_value = agent_response

    with patch("backend.voice.voice_agent.transcribe", return_value="spoken request") as stt:
        result = run_voice_session(recorder=recorder, agent=agent)

    assert isinstance(result, VoiceSessionResult)
    assert result.transcript == "spoken request"
    assert result.agent_response is agent_response
    recorder.assert_called_once_with(sample_rate=16000)
    stt.assert_called_once_with(b"wav-audio", filename="mic_recording.wav")
    agent.run.assert_called_once()
    assert agent.run.call_args.kwargs["user_message"] == "spoken request"


def test_voice_session_rejects_empty_transcription():
    with patch("backend.voice.voice_agent.transcribe", return_value=""):
        with pytest.raises(RuntimeError, match="empty transcription"):
            run_voice_session(recorder=Mock(return_value=b"wav-audio"), agent=Mock())


def test_microphone_failure_closes_stream():
    stream = Mock()
    stream.start.side_effect = RuntimeError("device unavailable")

    with pytest.raises(RuntimeError, match="device unavailable"):
        record_microphone(stream_factory=lambda **kwargs: stream)

    stream.close.assert_called_once()
    stream.stop.assert_not_called()


def test_microphone_interruption_closes_stream():
    stream = Mock()

    with pytest.raises(KeyboardInterrupt):
        record_microphone(
            input_func=Mock(side_effect=KeyboardInterrupt),
            stream_factory=lambda **kwargs: stream,
        )

    stream.stop.assert_called_once()
    stream.close.assert_called_once()
