import { useCallback, useEffect, useRef, useState } from "react";
import * as agentsApi from "@/lib/api/resources/agents";
import type { AgentReadyStatus as ReadyStatus } from "@/lib/api/resources/agents";
import type { ThreadResourceSettings } from "@/types/threads";

type AgentReadyStatus = ReadyStatus | null;

interface AgentReadyState {
	ready: boolean | null;
	acceptsFiles: boolean | null;
	disconnectedServers: string[];
	status: AgentReadyStatus;
	/** Human-readable reason, set with `sandbox_unavailable`. */
	detail: string | null;
	refetch: () => void;
}

export function useAgentConnectionStatus(
	agentId: string | undefined,
	resources?: ThreadResourceSettings,
): AgentReadyState {
	const [ready, setReady] = useState<boolean | null>(null);
	const [acceptsFiles, setAcceptsFiles] = useState(false);
	const [disconnectedServers, setDisconnectedServers] = useState<string[]>([]);
	const [status, setStatus] = useState<AgentReadyStatus>(null);
	const [detail, setDetail] = useState<string | null>(null);
	const [resolvedRequestKey, setResolvedRequestKey] = useState<string | null>(
		null,
	);
	const requestIdRef = useRef(0);
	const requestKey = [
		agentId ?? "",
		...(resources?.disabledMcpServerIds ?? []),
		"|",
		...(resources?.disabledSandboxIds ?? []),
		"|",
		...(resources?.disabledSubagentIds ?? []),
	].join(",");

	const refetch = useCallback(() => {
		const requestedAgentId = agentId;
		const requestedKey = requestKey;
		const requestId = ++requestIdRef.current;
		if (!requestedAgentId) return;
		agentsApi
			.getAgentReadiness(requestedAgentId, resources)
			.then((readiness) => {
				if (requestId !== requestIdRef.current) return;
				setReady(readiness.ready);
				setAcceptsFiles(readiness.acceptsFiles);
				setDisconnectedServers(readiness.disconnectedServers);
				setStatus(readiness.status);
				setDetail(readiness.detail ?? null);
				setResolvedRequestKey(requestedKey);
			})
			.catch(() => {
				if (requestId !== requestIdRef.current) return;
				setReady(false);
				setAcceptsFiles(false);
				setDisconnectedServers([]);
				setStatus("disconnected");
				setDetail(null);
				setResolvedRequestKey(requestedKey);
			});
	}, [agentId, requestKey, resources]);

	useEffect(() => {
		refetch();
		return () => {
			requestIdRef.current += 1;
		};
	}, [refetch]);

	const belongsToCurrentRequest = resolvedRequestKey === requestKey;
	return {
		ready: belongsToCurrentRequest ? ready : null,
		acceptsFiles: belongsToCurrentRequest ? acceptsFiles : null,
		disconnectedServers: belongsToCurrentRequest ? disconnectedServers : [],
		status: belongsToCurrentRequest ? status : null,
		detail: belongsToCurrentRequest ? detail : null,
		refetch,
	};
}
