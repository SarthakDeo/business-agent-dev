"use client";

import { useEffect, useState, useRef } from "react";
import {
  Mic,
  Square,
  Sparkles,
  Bot,
  AlertCircle,
  CheckCircle2,
  Workflow,
  Zap,
  ArrowRight,
  ShieldAlert,
  Loader2,
  Volume2,
} from "lucide-react";
import { clsx } from "clsx";
import { VoiceState, PendingConfirmationInfo } from "@/lib/types";
import { ModeBadge } from "./mode-badge";
import { ConfirmationCard } from "./confirmation-card";

interface VoiceHeroProps {
  state: VoiceState;
  transcript: string | null;
  currentMode?: string | null;
  pendingConfirmation: {
    runId: string;
    info: PendingConfirmationInfo;
  } | null;
  lastResponse?: {
    text: string;
    mode?: string;
    status?: string;
    automationId?: string;
  } | null;
  errorMessage?: string | null;
  audioLevel?: number;
  onToggleRecord: () => void;
  onConfirmAction: (approved: boolean) => void;
  onReset: () => void;
  isConfirming?: boolean;
}

export function VoiceHero({
  state,
  transcript,
  currentMode,
  pendingConfirmation,
  lastResponse,
  errorMessage,
  audioLevel = 0,
  onToggleRecord,
  onConfirmAction,
  onReset,
  isConfirming = false,
}: VoiceHeroProps) {
  // Synthesized visual sound wave heights
  const bars = [0.35, 0.65, 0.9, 0.75, 0.45];

  const isRecording = state === "LISTENING";
  const isBusy = state === "PROCESSING" || state === "THINKING" || state === "EXECUTING";

  return (
    <section
      aria-label="Voice Interaction Hero"
      className="w-full flex flex-col items-center justify-center text-center py-6 px-4"
    >
      {/* 1. Header Greeting / Value Proposition */}
      <div className="mb-6 space-y-1.5 max-w-lg">
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          How can I help your business today?
        </h1>
        <p className="text-xs sm:text-sm text-slate-400">
          Speak naturally. Voice2Flow understands your intent, builds the workflow, and gets the work done.
        </p>
      </div>

      {/* 2. Main Microphone Button with Animated Ripple / Waves */}
      <div className="relative my-4 flex items-center justify-center">
        {/* Animated outer rings when listening */}
        {isRecording && (
          <>
            <span
              className="absolute h-36 w-36 rounded-full bg-rose-500/20 animate-ping opacity-75 pointer-events-none"
              style={{ animationDuration: "1.8s" }}
            />
            <span className="absolute h-44 w-44 rounded-full bg-rose-500/10 animate-pulse pointer-events-none" />
          </>
        )}

        {/* Ambient glow when idle or thinking */}
        {state === "IDLE" && (
          <span className="absolute h-32 w-32 rounded-full bg-indigo-500/15 blur-xl pointer-events-none" />
        )}
        {state === "THINKING" && (
          <span className="absolute h-36 w-36 rounded-full bg-indigo-600/25 blur-xl animate-pulse pointer-events-none" />
        )}

        {/* The Primary Microphone Button */}
        <button
          type="button"
          onClick={onToggleRecord}
          disabled={isBusy || !!pendingConfirmation}
          aria-label={
            isRecording
              ? "Stop listening"
              : state === "CONFIRMATION"
              ? "Confirmation required above"
              : "Speak to Voice2Flow"
          }
          className={clsx(
            "relative z-10 h-24 w-24 sm:h-28 sm:w-28 rounded-full flex flex-col items-center justify-center transition-all duration-300 shadow-2xl focus:outline-none focus:ring-4 select-none",
            isRecording
              ? "bg-gradient-to-tr from-rose-600 to-red-500 text-white shadow-rose-600/40 ring-4 ring-rose-400 scale-105"
              : state === "PROCESSING"
              ? "bg-slate-900 border-2 border-violet-500 text-violet-400 shadow-violet-950/40"
              : state === "THINKING"
              ? "bg-slate-900 border-2 border-indigo-500 text-indigo-400 shadow-indigo-950/40 scale-100"
              : state === "CONFIRMATION"
              ? "bg-slate-900 border-2 border-amber-500 text-amber-400 shadow-amber-950/30 opacity-80 cursor-default"
              : state === "SUCCESS"
              ? "bg-emerald-600 text-white shadow-emerald-600/30 hover:bg-emerald-500"
              : state === "ERROR"
              ? "bg-slate-900 border-2 border-rose-500 text-rose-400 shadow-rose-950/40"
              : "bg-gradient-to-tr from-indigo-600 via-indigo-600 to-violet-600 text-white shadow-indigo-600/40 hover:scale-105 hover:shadow-indigo-500/50 focus:ring-indigo-500/50"
          )}
        >
          {isRecording ? (
            <Square className="h-9 w-9 fill-current animate-pulse" />
          ) : state === "PROCESSING" ? (
            <Loader2 className="h-9 w-9 animate-spin text-violet-400" />
          ) : state === "THINKING" ? (
            <Sparkles className="h-9 w-9 animate-pulse text-indigo-400" />
          ) : state === "SUCCESS" ? (
            <CheckCircle2 className="h-10 w-10 text-white" />
          ) : state === "ERROR" ? (
            <AlertCircle className="h-9 w-9 text-rose-400" />
          ) : (
            <Mic className="h-10 w-10 text-white" />
          )}

          <span className="text-[11px] font-bold tracking-wider uppercase mt-1">
            {isRecording
              ? "Stop"
              : state === "PROCESSING"
              ? "Prisma"
              : state === "THINKING"
              ? "Thinking"
              : state === "SUCCESS"
              ? "Ready"
              : "Speak"}
          </span>
        </button>
      </div>

      {/* 3. Live State Status Indicator */}
      <div
        role="status"
        aria-live="polite"
        className="mt-3 flex flex-col items-center justify-center min-h-[3rem]"
      >
        {isRecording && (
          <div className="flex flex-col items-center gap-2">
            <div className="flex items-center gap-1.5 text-rose-400 font-semibold text-sm">
              <span className="h-2 w-2 rounded-full bg-rose-400 animate-ping" />
              <span>Listening... Click to finish speaking</span>
            </div>
            {/* Audio Waveform visualization */}
            <div className="flex items-center gap-1 h-5 pt-1">
              {bars.map((bar, i) => {
                const dynamicHeight = Math.max(4, Math.round(bar * (16 + audioLevel * 24)));
                return (
                  <span
                    key={i}
                    className="w-1 rounded-full bg-rose-400/80 transition-all duration-75"
                    style={{ height: `${dynamicHeight}px` }}
                  />
                );
              })}
            </div>
          </div>
        )}

        {state === "PROCESSING" && (
          <div className="flex items-center gap-2 text-violet-300 font-semibold text-sm">
            <Loader2 className="h-4 w-4 animate-spin text-violet-400" />
            <span>Understanding you... Transcribing speech via Prisma STT</span>
          </div>
        )}

        {state === "THINKING" && (
          <div className="flex items-center gap-2 text-indigo-300 font-semibold text-sm">
            <Sparkles className="h-4 w-4 animate-spin text-indigo-400" />
            <span>Voice2Flow is thinking... Planning & validating permissions</span>
          </div>
        )}

        {state === "CONFIRMATION" && (
          <div className="flex items-center gap-2 text-amber-300 font-semibold text-sm">
            <ShieldAlert className="h-4 w-4 text-amber-400" />
            <span>Voice2Flow wants your approval to execute this action</span>
          </div>
        )}

        {state === "EXECUTING" && (
          <div className="flex items-center gap-2 text-blue-300 font-semibold text-sm">
            <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
            <span>Executing action through verified tool boundary...</span>
          </div>
        )}

        {state === "SUCCESS" && (
          <div className="flex items-center gap-1.5 text-emerald-300 font-semibold text-sm">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span>Done ✓ Ready for your next spoken request</span>
          </div>
        )}

        {state === "ERROR" && (
          <div className="flex flex-col items-center gap-1.5">
            <div className="flex items-center gap-1.5 text-rose-300 font-semibold text-sm">
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
              <span>{errorMessage || "Voice request could not be processed"}</span>
            </div>
            <button
              onClick={onReset}
              className="text-xs text-indigo-400 hover:text-indigo-300 underline font-medium"
            >
              Try speaking again
            </button>
          </div>
        )}

        {state === "IDLE" && (
          <div className="text-slate-400 text-xs sm:text-sm font-medium">
            Click microphone and speak naturally
          </div>
        )}
      </div>

      {/* 4. Live Transcript Section ("You said ...") */}
      {transcript && (
        <div className="w-full max-w-2xl mt-4 rounded-2xl bg-slate-900/90 border border-slate-800 p-4 sm:p-5 shadow-lg text-left animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center justify-between gap-2 mb-2 pb-2 border-b border-slate-800/80">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-md bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-300 text-xs">
                <Mic className="h-3.5 w-3.5" />
              </div>
              <span className="text-xs font-bold uppercase tracking-wider text-indigo-300">
                You said
              </span>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">
              Prisma STT Transcript
            </span>
          </div>

          <p className="text-sm sm:text-base text-slate-100 font-medium italic leading-relaxed">
            "{transcript}"
          </p>

          {/* Dynamic mode badge that appears AFTER understanding */}
          {currentMode && (
            <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-400">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold text-slate-400">Understood as:</span>
                <ModeBadge mode={currentMode} size="xs" showDescription />
              </div>
            </div>
          )}
        </div>
      )}

      {/* 5. Voice -> Flow & Confirmation Experience */}
      {pendingConfirmation && (
        <div className="w-full max-w-2xl mt-4 text-left animate-in fade-in slide-in-from-top-2 duration-200">
          {/* Flow Understanding Header */}
          <div className="mb-2 p-3 rounded-xl bg-indigo-950/40 border border-indigo-800/50 flex items-center justify-between text-xs text-indigo-200">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-indigo-400" />
              <span className="font-semibold">
                Voice2Flow understood:{" "}
                <span className="text-white">
                  {pendingConfirmation.info.mode === "AUTOMATE"
                    ? "Autonomous n8n Workflow"
                    : "Direct Operational Action"}
                </span>
              </span>
            </div>
            <ModeBadge mode={pendingConfirmation.info.mode || "AUTOMATE"} size="xs" />
          </div>

          {/* Embedded Security Confirmation Card */}
          <ConfirmationCard
            runId={pendingConfirmation.runId}
            info={pendingConfirmation.info}
            onConfirm={onConfirmAction}
            loading={isConfirming}
          />
        </div>
      )}

      {/* 6. Success / Executed Result Callout (if action completed without pending confirmation) */}
      {!pendingConfirmation && lastResponse && state === "SUCCESS" && (
        <div className="w-full max-w-2xl mt-4 p-4 rounded-xl bg-slate-900 border border-emerald-500/30 text-left text-xs space-y-2">
          <div className="flex items-center justify-between text-emerald-400 font-semibold">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              <span>Voice2Flow Response</span>
            </div>
            {lastResponse.mode && <ModeBadge mode={lastResponse.mode} size="xs" />}
          </div>
          <p className="text-slate-200 text-xs sm:text-sm leading-relaxed whitespace-pre-wrap">
            {lastResponse.text}
          </p>
        </div>
      )}
    </section>
  );
}
