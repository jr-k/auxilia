import type { Workspace } from "@/types/workspaces";

export interface MCPOAuthAuthorization {
	client: {
		name: string;
		uri: string | null;
		logoUri: string | null;
	};
	scopes: string[];
	expiresAt: string;
	workspaces: Workspace[];
	activeWorkspaceId: string | null;
}

export interface MCPOAuthRedirect {
	redirectUrl: string;
}
