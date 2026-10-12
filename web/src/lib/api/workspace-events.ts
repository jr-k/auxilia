import { API_BASE_URL } from "@/lib/api/client";

export function openWorkspaceEvents(): EventSource {
  return new EventSource(`${API_BASE_URL}/workspace-events/`, {
    withCredentials: true,
  });
}
