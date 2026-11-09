"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import {
  Bot,
  RefreshCw,
  Copy,
  Check,
  Keyboard,
  History,
  ChevronDown,
  ChevronUp,
  Volume2,
} from "lucide-react";
import { clsx } from "clsx";
import { ChatMessage as ChatMessageType, PendingConfirmationInfo, VoiceState } from "@/lib/types";
import { useSendAgentChat, useConfirmAgentAction, useTranscribeAudio } from "@/lib/hooks";
import { formatAgentErrorMessage } from "@/lib/utils";
import { AudioRecorder } from "@/lib/audio-recorder";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import { StarterPrompts } from "./starter-prompts";
import { ErrorMessage } from "./error-message";
import { ModeBadge } from "./mode-badge";
import { VoiceHero } from "./voice-hero";

const INITIAL_WELCOME: ChatMessageType = {
  id: "welcome_msg",
  role: "assistant",
  content:
    "Hello! I am your Voice2Flow AI Business Agent. Speak naturally to query data (ASK), dispatch operational actions (DO), or build autonomous workflows (AUTOMATE).",
  mode: "ASK",
  status: "completed",
  timestamp: new Date().toISOString(),
};

export function AgentShell() {
  const searchParams = useSearchParams();
  const initialPromptFromUrl = searchParams.get("prompt");

  // Conversation & Agent States
  const [messages, setMessages] = useState<ChatMessageType[]>([INITIAL_WELCOME]);
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [currentRunId, setCurrentRunId] = useState<string | undefined>(undefined);
  const [activePending, setActivePending] = useState<{
    runId: string;
    info: PendingConfirmationInfo;
  } | null>(null);
  const [errorState, setErrorState] = useState<{
    message: string;
    code?: string | null;
  } | null>(null);
  const [copiedConvId, setCopiedConvId] = useState(false);
  const [currentMode, setCurrentMode] = useState<string>("ASK");

  // Voice Interaction States
  const [voiceState, setVoiceState] = useState<VoiceState>("IDLE");
  const [currentTranscript, setCurrentTranscript] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [showTextFallback, setShowTextFallback] = useState<boolean>(false);
  const [showHistory, setShowHistory] = useState<boolean>(true);
  const [lastResponseSummary, setLastResponseSummary] = useState<{
    text: string;
    mode?: string;
    status?: string;
    automationId?: string;
  } | null>(null);

  // Audio recording ref
  const recorderRef = useRef<AudioRecorder | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const initialPromptProcessed = useRef(false);

  // Mutations
  const sendMutation = useSendAgentChat();
  const confirmMutation = useConfirmAgentAction();
  const transcribeMutation = useTranscribeAudio();

  const isExecuting = sendMutation.isPending || confirmMutation.isPending || transcribeMutation.isPending;

  // Cleanup audio recorder on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      if (recorderRef.current) recorderRef.current.cancel();
    };
  }, []);

  // Handle message submission (voice or typed)
  const handleSendMessage = useCallback(
    async (messageText: string, isVoice: boolean = false) => {
      if (!messageText.trim() || sendMutation.isPending || !!activePending) return;

      setErrorState(null);
      setVoiceState("THINKING");

      const userMsg: ChatMessageType = {
        id: `user_${Date.now()}`,
        role: "user",
        content: messageText,
        isVoice,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg]);

      try {
        const response = await sendMutation.mutateAsync({
          message: messageText,
          conversationId,
        });

        setConversationId(response.conversation_id);
        setCurrentRunId(response.run_id);
        if (response.mode) setCurrentMode(response.mode);

        const hasPending =
          response.status === "awaiting_confirmation" && !!response.pending_confirmation;

        if (hasPending && response.pending_confirmation) {
          setActivePending({
            runId: response.run_id,
            info: response.pending_confirmation,
          });
          setVoiceState("CONFIRMATION");
        } else {
          setActivePending(null);
          setVoiceState(response.status === "error" ? "ERROR" : "SUCCESS");
        }

        const automationData = (response.execution_results?.automation as Record<string, unknown>) || null;
        const autoId = (automationData?.automation_id as string) || (automationData?.id as string) || undefined;

        setLastResponseSummary({
          text: response.response,
          mode: response.mode,
          status: response.status,
          automationId: autoId,
        });

        const agentMsg: ChatMessageType = {
          id: `agt_${Date.now()}`,
          role: "assistant",
          content: response.response,
          mode: response.mode,
          status: response.status,
          runId: response.run_id,
          conversationId: response.conversation_id,
          timestamp: new Date().toISOString(),
          pendingConfirmation: response.pending_confirmation,
          executionResults: response.execution_results,
          automationId: autoId,
          error: response.error,
          errorCode: response.error_code,
        };

        setMessages((prev) => [...prev, agentMsg]);
      } catch (err: unknown) {
        const friendlyMessage = formatAgentErrorMessage(err);
        setErrorState({ message: friendlyMessage });
        setVoiceState("ERROR");
        setMessages((prev) => [
          ...prev,
          {
            id: `err_${Date.now()}`,
            role: "assistant",
            content: friendlyMessage,
            status: "error",
            timestamp: new Date().toISOString(),
            error: friendlyMessage,
          },
        ]);
      }
    },
    [conversationId, sendMutation, activePending]
  );

  // Toggle Microphone Recording
  const handleToggleRecord = async () => {
    // If currently recording: STOP and transcribe
    if (voiceState === "LISTENING") {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      setAudioLevel(0);
      setVoiceState("PROCESSING");

      try {
        if (!recorderRef.current) throw new Error("Audio recorder is not initialized");
        const recorder = recorderRef.current;
        const browserFallback = recorder.getBrowserTranscript();
        const audioBlob = await recorder.stop();
        recorderRef.current = null;

        let finalTranscript = "";
        try {
          // 1. Primary: Call Voice2Flow Prisma STT endpoint
          const res = await transcribeMutation.mutateAsync(audioBlob);
          finalTranscript = res.transcript;
        } catch (sttErr: unknown) {
          // 2. Fallback: If Prisma STT is unconfigured/offline, use captured browser speech
          if (browserFallback && browserFallback.trim()) {
            finalTranscript = browserFallback.trim();
          } else {
            throw sttErr;
          }
        }

        if (!finalTranscript || !finalTranscript.trim()) {
          setVoiceState("ERROR");
          setErrorState({
            message: "Could not detect clear speech. Please speak closer to your microphone.",
          });
          return;
        }

        // Show live transcript immediately
        setCurrentTranscript(finalTranscript.trim());

        // Process transcript through Agent pipeline
        await handleSendMessage(finalTranscript.trim(), true);
      } catch (err: unknown) {
        const msg = formatAgentErrorMessage(err);
        setErrorState({ message: msg });
        setVoiceState("ERROR");
      }
      return;
    }

    // If IDLE, SUCCESS, or ERROR: START recording
    if (voiceState === "IDLE" || voiceState === "SUCCESS" || voiceState === "ERROR") {
      setErrorState(null);
      setCurrentTranscript(null);

      try {
        const recorder = new AudioRecorder();
        await recorder.start();
        recorderRef.current = recorder;
        setVoiceState("LISTENING");

        // Start real-time audio volume polling
        pollIntervalRef.current = setInterval(() => {
          if (recorderRef.current && recorderRef.current.isRecording()) {
            setAudioLevel(recorderRef.current.getAudioLevel());
          }
        }, 80);
      } catch (err: unknown) {
        const msg = formatAgentErrorMessage(err);
        setErrorState({ message: msg });
        setVoiceState("ERROR");
      }
    }
  };

  // Handle confirmation approve/reject
  const handleConfirmAction = async (approved: boolean) => {
    if (!activePending || !conversationId || confirmMutation.isPending) return;

    setErrorState(null);
    setVoiceState("EXECUTING");
    const { runId, info } = activePending;

    try {
      const result = await confirmMutation.mutateAsync({
        runId,
        conversationId,
        approved,
      });

      setActivePending(null);
      setCurrentRunId(result.run_id);
      setVoiceState(result.status === "error" ? "ERROR" : "SUCCESS");

      setLastResponseSummary({
        text: result.response,
        mode: info.mode || currentMode,
        status: result.status,
      });

      const confirmMsg: ChatMessageType = {
        id: `conf_${Date.now()}`,
        role: "assistant",
        content: result.response,
        mode: info.mode || currentMode,
        status: result.status,
        runId: result.run_id,
        conversationId: result.conversation_id,
        timestamp: new Date().toISOString(),
        executionResults: result.execution_results,
        error: result.error,
        errorCode: result.error_code,
      };

      setMessages((prev) => [...prev, confirmMsg]);
    } catch (err: unknown) {
      const friendlyMessage = formatAgentErrorMessage(err);
      setErrorState({ message: friendlyMessage });
      setVoiceState("ERROR");
      const errStr = String(err).toLowerCase();
      if (errStr.includes("404") || errStr.includes("409") || errStr.includes("no pending operation")) {
        setActivePending(null);
      }
    }
  };

  // Handle starter prompt selection
  const handleSelectStarterPrompt = (prompt: string) => {
    setCurrentTranscript(prompt);
    handleSendMessage(prompt, false);
  };

  // Reset conversation to fresh session
  const handleResetConversation = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    if (recorderRef.current) {
      recorderRef.current.cancel();
      recorderRef.current = null;
    }
    setMessages([INITIAL_WELCOME]);
    setConversationId(undefined);
    setCurrentRunId(undefined);
    setActivePending(null);
    setErrorState(null);
    setCurrentTranscript(null);
    setLastResponseSummary(null);
    setVoiceState("IDLE");
    setCurrentMode("ASK");
  };

  const copyConversationId = () => {
    if (!conversationId) return;
    navigator.clipboard.writeText(conversationId);
    setCopiedConvId(true);
    setTimeout(() => setCopiedConvId(false), 2000);
  };

  // Process initial URL parameter if present
  useEffect(() => {
    if (initialPromptFromUrl && !initialPromptProcessed.current) {
      initialPromptProcessed.current = true;
      setCurrentTranscript(initialPromptFromUrl);
      handleSendMessage(initialPromptFromUrl, false);
    }
  }, [initialPromptFromUrl, handleSendMessage]);

  const pastMessages = messages.filter((m) => m.id !== "welcome_msg");

  return (
    <div className="flex flex-col min-h-[calc(100vh-8.5rem)] max-w-5xl mx-auto bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl overflow-hidden">
      {/* 1. Header Bar */}
      <header className="h-16 px-6 border-b border-slate-800 bg-slate-900/90 backdrop-blur flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shadow-sm">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white tracking-tight">Voice2Flow Agent</h2>
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800/80">
                Voice First
              </span>
              <ModeBadge mode={currentMode} size="xs" />
            </div>
            <div className="text-[11px] text-slate-400">
              Voice-to-Flow autonomous business intelligence & automation
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {conversationId ? (
            <button
              onClick={copyConversationId}
              title="Copy active conversation ID"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 border border-slate-700 text-xs font-mono transition-colors"
            >
              {copiedConvId ? (
                <Check className="h-3 w-3 text-emerald-400" />
              ) : (
                <Copy className="h-3 w-3 text-slate-400" />
              )}
              <span className="hidden sm:inline">id:</span>
              <span>{conversationId.slice(0, 10)}...</span>
            </button>
          ) : (
            <span className="text-xs font-mono text-slate-500 bg-slate-900 px-2.5 py-1 rounded-md border border-slate-800">
              Ready
            </span>
          )}

          <button
            onClick={handleResetConversation}
            disabled={isExecuting}
            title="Start new conversation"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">New Session</span>
          </button>
        </div>
      </header>

      {/* 2. Scrollable Body Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 scroll-smooth">
        {/* Error notification if top-level action failed */}
        {errorState && (
          <ErrorMessage
            error={errorState.message}
            errorCode={errorState.code}
            onDismiss={() => setErrorState(null)}
          />
        )}

        {/* PRIMARY HERO AREA: Visual Microphone & Voice Interaction */}
        <VoiceHero
          state={voiceState}
          transcript={currentTranscript}
          currentMode={currentMode}
          pendingConfirmation={activePending}
          lastResponse={lastResponseSummary}
          errorMessage={errorState?.message}
          audioLevel={audioLevel}
          onToggleRecord={handleToggleRecord}
          onConfirmAction={handleConfirmAction}
          onReset={() => setVoiceState("IDLE")}
          isConfirming={confirmMutation.isPending}
        />

        {/* STARTER VOICE PROMPTS (Shown when idle or ready) */}
        {!activePending && voiceState !== "LISTENING" && (
          <StarterPrompts
            onSelectPrompt={handleSelectStarterPrompt}
            disabled={isExecuting}
          />
        )}

        {/* 3. SECONDARY TEXT FALLBACK ACCORDION */}
        <div className="max-w-3xl mx-auto pt-2">
          <div className="flex items-center justify-between border-t border-slate-800/80 pt-3">
            <button
              type="button"
              onClick={() => setShowTextFallback((prev) => !prev)}
              className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-indigo-400 transition-colors"
            >
              <Keyboard className="h-4 w-4" />
              <span>{showTextFallback ? "Hide text fallback" : "Prefer typing? Use text instead"}</span>
              {showTextFallback ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>

            {pastMessages.length > 0 && (
              <button
                type="button"
                onClick={() => setShowHistory((prev) => !prev)}
                className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
              >
                <History className="h-3.5 w-3.5" />
                <span>
                  {showHistory ? "Hide" : "Show"} Session History ({pastMessages.length})
                </span>
              </button>
            )}
          </div>

          {/* Collapsible Text Input Area */}
          {showTextFallback && (
            <div className="mt-3 p-4 rounded-xl bg-slate-900/60 border border-slate-800 animate-in fade-in duration-200">
              <ChatInput
                onSend={(text) => handleSendMessage(text, false)}
                loading={isExecuting}
                disabled={!!activePending}
                disabledReason={
                  activePending
                    ? "Approval required above before submitting new requests..."
                    : undefined
                }
              />
            </div>
          )}
        </div>

        {/* 4. CONVERSATION AUDIT & HISTORY STREAM */}
        {pastMessages.length > 0 && showHistory && (
          <div className="max-w-3xl mx-auto space-y-3 pt-4 border-t border-slate-800/60 animate-in fade-in duration-150">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400 pb-1">
              <History className="h-3.5 w-3.5 text-indigo-400" />
              <span>Session History</span>
            </div>

            <div className="space-y-3">
              {pastMessages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
