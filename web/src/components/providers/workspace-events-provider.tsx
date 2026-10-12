"use client";

import { useEffect, type ReactNode } from "react";
import { toast } from "sonner";

import { openWorkspaceEvents } from "@/lib/api/workspace-events";
import { useWorkspaceEventsStore } from "@/stores/workspace-events-store";
import { useWorkspacesStore } from "@/stores/workspaces-store";
import { isWorkspaceInvalidation } from "@/types/workspace-events";

export function WorkspaceEventsProvider({
  children,
}: {
  children: ReactNode;
}) {
  const workspaceId = useWorkspacesStore((state) => state.activeWorkspaceId);

  useEffect(() => {
    if (workspaceId === null) return;

    const store = useWorkspaceEventsStore.getState();
    store.reset();
    store.setConnection("connecting");
    const source = openWorkspaceEvents();

    source.onopen = () => {
      useWorkspaceEventsStore.getState().setConnection("connected");
    };
    source.onerror = () => {
      useWorkspaceEventsStore.getState().setConnection("disconnected");
    };

    const handleSync = () => {
      useWorkspaceEventsStore.getState().sync();
    };
    const handleInvalidation = (raw: Event) => {
      if (!(raw instanceof MessageEvent)) return;
      try {
        const event: unknown = JSON.parse(String(raw.data));
        if (isWorkspaceInvalidation(event)) {
          if (event.kind === "notifications" && event.payload) {
            const { title, body, url } = event.payload;
            if (
              document.hidden &&
              "Notification" in window &&
              Notification.permission === "granted"
            ) {
              const notification = new Notification(title, {
                body,
                tag: event.eventKey ?? (raw.lastEventId || undefined),
              });
              if (url) {
                notification.onclick = () => {
                  window.focus();
                  window.location.assign(url);
                  notification.close();
                };
              }
            } else {
              toast(title, {
                id: event.eventKey ?? (raw.lastEventId || undefined),
                description: body,
                action: url
                  ? {
                      label: "Open",
                      onClick: () => {
                        window.location.assign(url);
                      },
                    }
                  : undefined,
              });
            }
          }
          useWorkspaceEventsStore.getState().invalidate(event);
        }
      } catch {
        // Ignore malformed events; the next sync reconciles all snapshots.
      }
    };

    source.addEventListener("sync", handleSync);
    source.addEventListener("invalidate", handleInvalidation);
    return () => {
      source.removeEventListener("sync", handleSync);
      source.removeEventListener("invalidate", handleInvalidation);
      source.close();
      useWorkspaceEventsStore.getState().reset();
    };
  }, [workspaceId]);

  return children;
}
