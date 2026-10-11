import { api } from "@/lib/api/client";
import type {
	MCPOAuthAuthorization,
	MCPOAuthRedirect,
} from "@/types/mcp-oauth";

const authorizationPath = (request: string) =>
	`/mcp/oauth/authorizations/${encodeURIComponent(request)}`;

export async function getAuthorization(
	request: string,
): Promise<MCPOAuthAuthorization> {
	const response = await api.get<MCPOAuthAuthorization>(
		authorizationPath(request),
	);
	return response.data;
}

export async function approveAuthorization(
	request: string,
	workspaceId: string,
): Promise<MCPOAuthRedirect> {
	const response = await api.post<MCPOAuthRedirect>(
		`${authorizationPath(request)}/approve`,
		{ workspaceId },
	);
	return response.data;
}

export async function denyAuthorization(
	request: string,
): Promise<MCPOAuthRedirect> {
	const response = await api.post<MCPOAuthRedirect>(
		`${authorizationPath(request)}/deny`,
	);
	return response.data;
}
