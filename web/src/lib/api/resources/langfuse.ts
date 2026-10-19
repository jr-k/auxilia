import { api } from "@/lib/api/client";

export interface LangfusePromptVersion {
	version: number;
	labels: string[];
	commitMessage: string | null;
	text: string;
	author: string | null;
	createdAt: string | null;
}

export interface LangfusePrompt {
	production: LangfusePromptVersion | null;
	diverged: boolean;
}

export async function isLangfuseEnabled(): Promise<boolean> {
	try {
		const response = await api.get<{ enabled: boolean }>("/integrations/langfuse");
		return response.data.enabled;
	} catch {
		return false;
	}
}

export async function getLangfusePrompt(
	agentId: string,
): Promise<LangfusePrompt> {
	const response = await api.get<LangfusePrompt>(
		`/agents/${agentId}/langfuse-prompt`,
	);
	return response.data;
}

export async function listLangfuseVersions(
	agentId: string,
): Promise<LangfusePromptVersion[]> {
	const response = await api.get<LangfusePromptVersion[]>(
		`/agents/${agentId}/langfuse-prompt/versions`,
	);
	return response.data;
}

export async function publishLangfusePrompt(
	agentId: string,
	commitMessage: string | null,
): Promise<LangfusePromptVersion> {
	const response = await api.post<LangfusePromptVersion>(
		`/agents/${agentId}/langfuse-prompt/publish`,
		{ commitMessage },
	);
	return response.data;
}

export async function promoteLangfuseVersion(
	agentId: string,
	version: number,
): Promise<LangfusePromptVersion> {
	const response = await api.post<LangfusePromptVersion>(
		`/agents/${agentId}/langfuse-prompt/versions/${version}/promote`,
	);
	return response.data;
}
