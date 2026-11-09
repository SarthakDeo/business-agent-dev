"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Bot, RefreshCw, Sparkles, AlertCircle, Copy, Check } from "lucide-react";
import { ChatMessage as ChatMessageType, PendingConfirmationInfo } from "@/lib/types";
import { useSendAgentChat, useConfirmAgentAction } from "@/lib/hooks";
import { formatAgentErrorMessage } from "@/lib/utils";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import { ConfirmationCard } from "./confirmation-card";
import { StarterPrompts } from "./starter-prompts";
import { TypingIndicator } from "./typing-indicator";
import { ErrorMessage } from "./error-message";
import { ModeBadge } from "./mode-badge";
import { StatusBadge } from "./status-badge";

const INITIAL_WELCOME: ChatMessageType = {
  id: "welcome_msg",
  role: "assistant",
  content:
    "Hello! I am your Voice2Flow AI Business Agent. I coordinate business intelligence (ASK), operational tool actions (DO), and autonomous n8n workflows (AUTOMATE) with full human-in-the-loop security. What would you like to achieve today?",
  mode: "ASK",
  status: "completed",
  timestamp: new Date().toISOString(),
};

export function AgentShell() {
  const searchParams = useSearchParams();
  const initialPromptFromUrl = searchParams.get("prompt");

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

  const scrollRef = useRef<HTMLDivElement>(null);
  const initialPromptProcessed = useRef(false);

  const sendMutation = useSendAgentChat();
  const confirmMutation = useConfirmAgentAction();

  const isExecuting = sendMutation.isPending || confirmMutation.isPending;

  // Auto-scroll to bottom of chat
  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, activePending, isExecuting, scrollToBottom]);

  // Handle message submission
  const handleSendMessage = useCallback(
    async (messageText: string) => {
      if (!messageText.trim() || isExecuting || activePending) return;

      setErrorState(null);

      const userMsg: ChatMessageType = {
        id: `user_${Date.now()}`,
        role: "user",
        content: messageText,
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
        } else {
          setActivePending(null);
        }

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
          error: response.error,
          errorCode: response.error_code,
        };

        setMessages((prev) => [...prev, agentMsg]);
      } catch (err: unknown) {
        const friendlyMessage = formatAgentErrorMessage(err);
        setErrorState({ message: friendlyMessage });
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
    [conversationId, isExecuting, activePending, sendMutation]
  );

  // Handle initial prompt from URL (?prompt=...)
  useEffect(() => {
    if (initialPromptFromUrl && !initialPromptProcessed.current) {
      initialPromptProcessed.current = true;
      handleSendMessage(initialPromptFromUrl);
    }
  }, [initialPromptFromUrl, handleSendMessage]);

  // Handle confirmation approve/reject
  const handleConfirmAction = async (approved: boolean) => {
    if (!activePending || !conversationId || isExecuting) return;

    setErrorState(null);
    const { runId, info } = activePending;

    try {
      const result = await confirmMutation.mutateAsync({
        runId,
        conversationId,
        approved,
      });

      setActivePending(null);
      setCurrentRunId(result.run_id);

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
      // If confirmation failed because it expired or was already processed, clear the activePending lock
      const errStr = String(err).toLowerCase();
      if (errStr.includes("404") || errStr.includes("409") || errStr.includes("no pending operation")) {
        setActivePending(null);
      }
    }
  };

  // Reset conversation to fresh session
  const handleResetConversation = () => {
    setMessages([INITIAL_WELCOME]);
    setConversationId(undefined);
    setCurrentRunId(undefined);
    setActivePending(null);
    setErrorState(null);
    setCurrentMode("ASK");
  };

  const copyConversationId = () => {
    if (!conversationId) return;
    navigator.clipboard.writeText(conversationId);
    setCopiedConvId(true);
    setTimeout(() => setCopiedConvId(false), 2000);
  };

  const hasUserMessages = messages.some((m) => m.role === "user");

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-5xl mx-auto bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl overflow-hidden">
      {/* Top Header Bar */}
      <header className="h-16 px-6 border-b border-slate-800 bg-slate-900/90 backdrop-blur flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shadow-sm">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white tracking-tight">Voice2Flow Agent</h2>
              <ModeBadge mode={currentMode} size="xs" showDescription />
            </div>
            <div className="text-[11px] text-slate-400">
              Autonomous business orchestrator with human confirmation gate
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
              New Session
            </span>
          )}

          <button
            onClick={handleResetConversation}
            disabled={isExecuting}
            title="Start new conversation"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">New Chat</span>
          </button>
        </div>
      </header>

      {/* Main Chat Scroll Area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 scroll-smooth"
      >
        {/* If no user messages yet, display Starter Prompts */}
        {!hasUserMessages && (
          <StarterPrompts
            onSelectPrompt={handleSendMessage}
            disabled={isExecuting || !!activePending}
          />
        )}

        {/* Message Feed */}
        {hasUserMessages &&
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

        {/* Active Confirmation Card */}
        {activePending && (
          <div className="py-2">
            <ConfirmationCard
              runId={activePending.runId}
              info={activePending.info}
              onConfirm={handleConfirmAction}
              loading={confirmMutation.isPending}
            />
          </div>
        )}

        {/* Typing indicator while Agent / Gemini is thinking */}
        {sendMutation.isPending && (
          <TypingIndicator label="Voice2Flow is planning, validating permissions, and preparing tools..." />
        )}

        {/* Error banner if top-level action failed */}
        {errorState && (
          <ErrorMessage
            error={errorState.message}
            errorCode={errorState.code}
            onDismiss={() => setErrorState(null)}
          />
        )}
      </div>

      {/* Bottom Input Area */}
      <footer className="p-4 bg-slate-900/60 border-t border-slate-800 shrink-0">
        <ChatInput
          onSend={handleSendMessage}
          loading={isExecuting}
          disabled={!!activePending}
          disabledReason={
            activePending
              ? "Human approval required above before sending further instructions..."
              : undefined
          }
        />
      </footer>
    </div>
  );
}
