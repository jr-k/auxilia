import { create } from "zustand";
import { Agent, AgentOwner, BoundAgent } from "@/types/agents";
import { createOnce } from "@/lib/api/once";
import * as agentsApi from "@/lib/api/resources/agents";
import type { AgentWrite } from "@/lib/api/resources/agents";
import { getWorkspaceGeneration, isCurrentWorkspaceGeneration } from "@/lib/workspace-generation";
import { useSkillsStore } from "@/stores/skills-store";
import { useThreadsStore } from "@/stores/threads-store";
import { useTriggersStore } from "@/stores/triggers-store";

interface AgentsState {
	agents: Agent[];
	isInitialized: boolean;
	/** Load once; concurrent callers share the in-flight request. */
	fetchAgents: () => Promise<void>;
	/** Load again, after any in-flight load settles. */
	refreshAgents: () => Promise<void>;
	/** Re-read one agent from the server and merge it into the list. */
	refreshAgent: (agentId: string) => Promise<void>;

	// --- mutations: each owns its HTTP call *and* its cache update ---------
	createAgent: (payload: AgentWrite) => Promise<Agent>;
	saveAgentConfig: (agentId: string, payload: AgentWrite) => Promise<Agent>;
	/** Soft delete: the agent leaves the live list. */
	archiveAgent: (agentId: string) => Promise<void>;
	/** Un-archive: the live list is reloaded so the agent reappears in place. */
	restoreAgent: (agentId: string) => Promise<void>;
	permanentlyDeleteAgent: (agentId: string) => Promise<void>;

	// --- local cache edits, for callers whose HTTP call lives elsewhere ------
	addAgent: (agent: Agent) => void;
	updateAgent: (agentId: string, agent: Partial<Agent>) => void;
	removeAgent: (agentId: string) => void;
	removeMcpServerBinding: (mcpServerId: string) => void;
	updateOwnerSnapshot: (userId: string, owner: AgentOwner) => void;
}

const boundAgent = (agent: Agent): BoundAgent => ({
	id: agent.id,
	name: agent.name,
	emoji: agent.emoji ?? null,
	color: agent.color ?? null,
	imageRevision: agent.imageRevision ?? null,
});

export const useAgentsStore = create<AgentsState>((set, get) => {
	const loader = createOnce(async () => {
		const generation = getWorkspaceGeneration();
		try {
			const agents = await agentsApi.listAgents();
			if (isCurrentWorkspaceGeneration(generation)) {
				set({ agents, isInitialized: true });
			}
		} catch (error) {
			if (!isCurrentWorkspaceGeneration(generation)) return;
			console.error("Error fetching agents:", error);
			throw error;
		}
	});

	return {
		agents: [],
		isInitialized: false,
		fetchAgents: async () => {
			if (get().isInitialized) return;
			await loader.run();
		},
		refreshAgents: () => loader.refresh(),
		refreshAgent: async (agentId) => {
			const agent = await agentsApi.getAgent(agentId);
			get().updateAgent(agentId, agent);
		},

		createAgent: async (payload) => {
			const created = await agentsApi.createAgent(payload);
			get().addAgent(created);
			useSkillsStore.getState().syncAgentUsage(boundAgent(created), payload.skillIds);
			return created;
		},
		saveAgentConfig: async (agentId, payload) => {
			const saved = await agentsApi.saveAgentConfig(agentId, payload);
			get().updateAgent(agentId, saved);
			useSkillsStore.getState().syncAgentUsage(boundAgent(saved), payload.skillIds);
			return saved;
		},
		archiveAgent: async (agentId) => {
			await agentsApi.archiveAgent(agentId);
			get().removeAgent(agentId);
			useThreadsStore.getState().markAgentArchived(agentId);
		},
		restoreAgent: async (agentId) => {
			await agentsApi.restoreAgent(agentId);
			await loader.refresh();
			const restored = get().agents.find((agent) => agent.id === agentId);
			if (restored) {
				useThreadsStore.getState().markAgentRestored(agentId, restored.name);
			}
		},
		permanentlyDeleteAgent: async (agentId) => {
			await agentsApi.permanentlyDeleteAgent(agentId);
			get().removeAgent(agentId);
			set((state) => ({
				agents: state.agents.map((agent) => ({
					...agent,
					subagents: agent.subagents.filter((subagent) => subagent.id !== agentId),
				})),
			}));
			useThreadsStore.getState().removeThreadsForAgent(agentId);
			useTriggersStore.getState().removeTriggersForAgent(agentId);
			useSkillsStore.getState().removeAgentUsage(agentId);
		},
		addAgent: (agent) => {
			set((state) => ({ agents: [agent, ...state.agents] }));
		},
		updateAgent: (agentId, agent) => {
			set((state) => ({
				agents: state.agents.map((a) => (a.id === agentId ? { ...a, ...agent } : a)),
			}));
			const usagePatch: Partial<Omit<BoundAgent, "id">> = {};
			if (agent.name !== undefined) usagePatch.name = agent.name;
			if ("emoji" in agent) usagePatch.emoji = agent.emoji ?? null;
			if ("color" in agent) usagePatch.color = agent.color ?? null;
			if ("imageRevision" in agent) {
				usagePatch.imageRevision = agent.imageRevision ?? null;
			}
			if (Object.keys(usagePatch).length > 0) {
				useSkillsStore.getState().updateAgentUsage(agentId, usagePatch);
			}
		},
		removeAgent: (agentId) => {
			set((state) => ({
				agents: state.agents.filter((agent) => agent.id !== agentId),
			}));
		},
		removeMcpServerBinding: (mcpServerId) => {
			set((state) => ({
				agents: state.agents.map((agent) => ({
					...agent,
					mcpServers: agent.mcpServers.filter(
						(server) => server.mcpServerId !== mcpServerId,
					),
				})),
			}));
		},
		updateOwnerSnapshot: (userId, owner) => {
			set((state) => ({
				agents: state.agents.map((agent) =>
					agent.ownerId === userId ? { ...agent, owner } : agent,
				),
			}));
		},
	};
});
