import { Suspense } from "react";
import { AgentShell } from "@/components/agent/agent-shell";
import { Loader2 } from "lucide-react";

export const metadata = {
  title: "Voice2Flow Agent | Conversational Business Intelligence",
  description: "Interactive conversational interface for Voice2Flow AI Business Agent",
};

export default function AgentPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col items-center justify-center h-[calc(100vh-8.5rem)] text-slate-400 gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
          <span className="text-xs font-medium">Initializing Voice2Flow Agent...</span>
        </div>
      }
    >
      <AgentShell />
    </Suspense>
  );
}
