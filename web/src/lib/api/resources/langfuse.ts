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

export interface LangfusePublishDraft {
	configJson: string;
	labels: string[];
}

export interface LangfusePublishInput {
	commitMessage: string | null;
	label: string;
	/** Text keeps arbitrary config keys out of the API client's case conversion. */
	configJson: string;
}

export async function getLangfusePublishDraft(
	agentId: string,
): Promise<LangfusePublishDraft> {
	const response = await api.get<LangfusePublishDraft>(
		`/agents/${agentId}/langfuse-prompt/draft`,
	);
	return response.data;
}

export async function publishLangfusePrompt(
	agentId: string,
	input: LangfusePublishInput,
): Promise<LangfusePromptVersion> {
	const response = await api.post<LangfusePromptVersion>(
		`/agents/${agentId}/langfuse-prompt/publish`,
		input,
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
