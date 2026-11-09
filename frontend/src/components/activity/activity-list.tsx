"use client";

import { AuditEvent } from "@/lib/types";
import { ActivityEventItem } from "./activity-event";
import { ActivityEmptyState } from "./activity-empty-state";

interface ActivityListProps {
  events: AuditEvent[];
  searchQuery?: string;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function ActivityList({
  events,
  searchQuery,
  onRefresh,
  isRefreshing,
}: ActivityListProps) {
  if (events.length === 0) {
    return (
      <ActivityEmptyState
        title={searchQuery ? "No matching activity" : "No activity yet"}
        description={
          searchQuery
            ? `No audit events matched your search "${searchQuery}".`
            : "Voice2Flow audit events will appear here as you use the agent and automate your business."
        }
        onRefresh={onRefresh}
        isRefreshing={isRefreshing}
      />
    );
  }

  return (
    <div className="space-y-3">
      {events.map((event) => (
        <ActivityEventItem key={event.id} event={event} />
      ))}
    </div>
  );
}
