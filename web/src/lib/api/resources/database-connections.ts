import { api } from "@/lib/api/client";
import type {
	DBHubStatus,
	DatabaseConnection,
	DatabaseConnectionCreate,
	DatabaseConnectionUpdate,
} from "@/types/database-connections";

export async function listDatabaseConnections(): Promise<DatabaseConnection[]> {
	const response = await api.get<DatabaseConnection[]>("/database-connections");
	return response.data;
}

export async function getDatabaseConnection(
	connectionId: string,
	options: { cookie?: string } = {},
): Promise<DatabaseConnection> {
	const response = await api.get<DatabaseConnection>(
		`/database-connections/${connectionId}`,
		{ headers: options.cookie ? { Cookie: options.cookie } : undefined },
	);
	return response.data;
}

export async function createDatabaseConnection(
	payload: DatabaseConnectionCreate,
): Promise<DatabaseConnection> {
	const response = await api.post<DatabaseConnection>(
		"/database-connections",
		payload,
	);
	return response.data;
}

export async function updateDatabaseConnection(
	connectionId: string,
	payload: DatabaseConnectionUpdate,
): Promise<DatabaseConnection> {
	const response = await api.patch<DatabaseConnection>(
		`/database-connections/${connectionId}`,
		payload,
	);
	return response.data;
}

export async function deleteDatabaseConnection(
	connectionId: string,
	options: { detachAgents?: boolean } = {},
): Promise<void> {
	await api.delete(`/database-connections/${connectionId}`, {
		params: options.detachAgents ? { detachAgents: true } : undefined,
	});
}

export async function reconcileDatabaseConnection(
	connectionId: string,
): Promise<void> {
	await api.post(`/database-connections/${connectionId}/reconcile`);
}

export async function getDBHubStatus(): Promise<DBHubStatus> {
	const response = await api.get<DBHubStatus>("/database-connections/status");
	return response.data;
}
