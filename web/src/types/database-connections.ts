import type { ResourceVisibility } from "./visibility";

export type DatabaseEngine =
	| "sqlite"
	| "postgres"
	| "mysql"
	| "mariadb"
	| "sqlserver"
	| "oracle";

export type DatabaseConnectionStatus = "pending" | "ready" | "error";

export interface DatabaseConnection {
	id: string;
	mcpServerId: string;
	name: string;
	iconUrl: string;
	imageRevision?: string | null;
	description?: string | null;
	group?: string | null;
	engine: DatabaseEngine;
	host: string | null;
	port: number | null;
	database: string;
	username: string | null;
	sqliteFileId?: string | null;
	sqliteFileName?: string | null;
	sqliteStoredName?: string | null;
	sqliteRuntimePath?: string | null;
	sqliteFileSizeBytes?: number | null;
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
	group?: string | null;
	engine: DatabaseEngine;
	host?: string | null;
	port?: number | null;
	database?: string | null;
	username?: string | null;
	password?: string | null;
	sqliteFileId?: string | null;
	sslMode?: string | null;
	connectionTimeout?: number;
	queryTimeout?: number;
	readonly?: boolean;
	maxRows?: number;
	visibility?: ResourceVisibility;
	teamIds?: string[];
}

export type DatabaseConnectionUpdate = Partial<DatabaseConnectionCreate>;

export interface SQLiteFile {
	id: string;
	originalName: string;
	storedName: string;
	runtimePath: string;
	sizeBytes: number;
}

export interface DatabaseConnectorStatus {
	enabled: boolean;
	reachable: boolean;
	desiredRevision: number;
	appliedRevision: number;
	sourceCount: number;
	lastError?: string | null;
	lastAppliedAt?: string | null;
}
