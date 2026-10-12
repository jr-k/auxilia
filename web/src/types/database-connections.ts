import type { ResourceVisibility } from "./visibility";

export type DatabaseEngine =
	"postgres" | "mysql" | "mariadb" | "sqlserver" | "oracle";

export type DatabaseConnectionStatus = "pending" | "ready" | "error";

export interface DatabaseConnection {
	id: string;
	mcpServerId: string;
	name: string;
	description?: string | null;
	engine: DatabaseEngine;
	host: string;
	port: number;
	database: string;
	username: string;
	sslMode?: string | null;
	connectionTimeout: number;
	queryTimeout: number;
	readonly: boolean;
	maxRows: number;
	visibility: ResourceVisibility;
	teamIds: string[];
	status: DatabaseConnectionStatus;
	lastError?: string | null;
	hasPassword: boolean;
	desiredRevision: number;
	appliedRevision: number;
	lastAppliedAt?: string | null;
	createdAt: string;
	updatedAt: string;
}

export interface DatabaseConnectionCreate {
	name: string;
	description?: string | null;
	engine: DatabaseEngine;
	host: string;
	port: number;
	database: string;
	username: string;
	password: string;
	sslMode?: string | null;
	connectionTimeout?: number;
	queryTimeout?: number;
	readonly?: boolean;
	maxRows?: number;
	visibility?: ResourceVisibility;
	teamIds?: string[];
}

export type DatabaseConnectionUpdate = Partial<
	Omit<DatabaseConnectionCreate, "engine">
>;

export interface DBHubStatus {
	enabled: boolean;
	reachable: boolean;
	desiredRevision: number;
	appliedRevision: number;
	sourceCount: number;
	lastError?: string | null;
	lastAppliedAt?: string | null;
}
