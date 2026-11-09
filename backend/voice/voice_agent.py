"""Voice-to-agent orchestration."""

from collections.abc import Callable
from dataclasses import dataclass

from backend.agent import Agent, ConversationContext
from backend.agent.agent import AgentResponse
from backend.prisma import transcribe

from .microphone import record_microphone

VOICE_PERMISSIONS = [
    "crm.read",
    "crm.write",
    "gmail.read",
    "gmail.send",
    "slack.send",
]


@dataclass
class VoiceSessionResult:
    """Transcript and Agent response produced by one voice session."""

    transcript: str
    agent_response: AgentResponse


def run_voice_session(
    sample_rate: int = 16000,
    recorder: Callable[..., bytes] = record_microphone,
    agent: Agent | None = None,
):
    """Capture speech, transcribe it with Prisma, and send it to the agent."""
    audio_bytes = recorder(
        sample_rate=sample_rate,
    )
    transcript = transcribe(audio_bytes, filename="mic_recording.wav")
    if not transcript:
        raise RuntimeError("Prisma returned an empty transcription")

    voice_agent = agent or Agent()
    context = ConversationContext(user_id="voice-user", org_id="demo-org")
    agent_response = voice_agent.run(
        user_message=transcript,
        context=context,
        user_permissions=VOICE_PERMISSIONS,
    )
    return VoiceSessionResult(
        transcript=transcript,
        agent_response=agent_response,
    )


def main() -> None:
    print("=" * 60)
    print(" VOICE2FLOW LIVE VOICE AGENT TEST")
    print("=" * 60)
    input("\nPress [Enter] to start recording (or Ctrl+C to quit): ")

    print("\nTranscribing...")
    session = run_voice_session()
    print(f"\nTranscript: {session.transcript}")
    print(f"\nAgent Mode:   {session.agent_response.mode}")
    print(f"Agent Status: {session.agent_response.status}")
    print(f"\nAgent Response:\n{session.agent_response.response_text}")


if __name__ == "__main__":
    main()
