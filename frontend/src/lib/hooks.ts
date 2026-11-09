import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export function useSendAgentChat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ message, conversationId }: { message: string; conversationId?: string }) =>
      api.sendAgentChat(message, conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
      queryClient.invalidateQueries({ queryKey: ["recent-activity"] });
      queryClient.invalidateQueries({ queryKey: ["recent-executions"] });
    },
  });
}

export function useConfirmAgentAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      conversationId,
      approved,
    }: {
      runId: string;
      conversationId: string;
      approved: boolean;
    }) => api.confirmAgentAction(runId, conversationId, approved),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
      queryClient.invalidateQueries({ queryKey: ["recent-activity"] });
      queryClient.invalidateQueries({ queryKey: ["recent-executions"] });
    },
  });
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.getDashboardStats(),
    staleTime: 10_000,
    retry: 1,
  });
}

export function useRecentActivity(limit = 5) {
  return useQuery({
    queryKey: ["recent-activity", limit],
    queryFn: () => api.listActivity(limit, 0),
    staleTime: 5_000,
    retry: 1,
  });
}

export function useRecentExecutions(limit = 5) {
  return useQuery({
    queryKey: ["recent-executions", limit],
    queryFn: () => api.listExecutions(limit, 0),
    staleTime: 5_000,
    retry: 1,
  });
}

export function useActivity(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["activity", limit, offset],
    queryFn: () => api.listActivity(limit, offset),
    staleTime: 5_000,
    retry: 1,
  });
}

export function useExecutions(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["executions", limit, offset],
    queryFn: () => api.listExecutions(limit, offset),
    staleTime: 5_000,
    retry: 1,
  });
}


export function useIntegrationHealth() {
  return useQuery({
    queryKey: ["integration-health"],
    queryFn: () => api.listIntegrations(),
    staleTime: 15_000,
    retry: 1,
  });
}

export function useIntegrations() {
  return useQuery({
    queryKey: ["integrations"],
    queryFn: () => api.listIntegrations(),
    staleTime: 10_000,
    retry: 1,
  });
}

export function useConnectIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      integration,
      secret,
      accountIdentifier,
    }: {
      integration: string;
      secret: string;
      accountIdentifier?: string;
    }) => api.connectIntegration(integration, secret, accountIdentifier),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      queryClient.invalidateQueries({ queryKey: ["integration-health"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
}

export function useDisconnectIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (integration: string) => api.disconnectIntegration(integration),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      queryClient.invalidateQueries({ queryKey: ["integration-health"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
}

export function useApiHealth() {
  return useQuery({
    queryKey: ["api-health"],
    queryFn: () => api.getHealth(),
    staleTime: 30_000,
    retry: 1,
  });
}

export function useAutomationsList() {
  return useQuery({
    queryKey: ["automations"],
    queryFn: () => api.listAutomations(),
    staleTime: 10_000,
    retry: 1,
  });
}

export function useAutomationDetail(id: string) {
  return useQuery({
    queryKey: ["automation-detail", id],
    queryFn: () => api.getAutomation(id),
    enabled: Boolean(id),
    staleTime: 10_000,
    retry: (failureCount, error) => {
      if (error instanceof Error && error.message.includes("404")) return false;
      return failureCount < 1;
    },
  });
}
