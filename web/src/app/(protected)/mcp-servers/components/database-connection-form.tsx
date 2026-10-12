"use client";

import {
	AlertCircle,
	ArrowLeft,
	CheckCircle2,
	Database,
	Loader2,
	RefreshCw,
	Save,
	ShieldCheck,
	Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { VisibilityPicker } from "@/components/ui/visibility-picker";
import { getApiErrorMessage, toApiError } from "@/lib/api/errors";
import {
	createDatabaseConnection,
	deleteDatabaseConnection,
	getDatabaseConnection,
	reconcileDatabaseConnection,
	updateDatabaseConnection,
} from "@/lib/api/resources/database-connections";
import { useMcpServersStore } from "@/stores/mcp-servers-store";
import type {
	DatabaseConnection,
	DatabaseConnectionCreate,
	DatabaseEngine,
	DatabaseConnectionUpdate,
} from "@/types/database-connections";

const ENGINE_OPTIONS: Array<{
	value: DatabaseEngine;
	label: string;
	defaultPort: number;
}> = [
	{ value: "postgres", label: "PostgreSQL", defaultPort: 5432 },
	{ value: "mysql", label: "MySQL", defaultPort: 3306 },
	{ value: "mariadb", label: "MariaDB", defaultPort: 3306 },
	{ value: "sqlserver", label: "SQL Server", defaultPort: 1433 },
	{ value: "oracle", label: "Oracle", defaultPort: 1521 },
];

const STATUS_STYLES = {
	pending: {
		label: "Pending",
		icon: RefreshCw,
		className:
			"border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300",
	},
	ready: {
		label: "Ready",
		icon: CheckCircle2,
		className:
			"border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300",
	},
	error: {
		label: "Error",
		icon: AlertCircle,
		className:
			"border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300",
	},
} as const;

interface FormState {
	name: string;
	description: string;
	engine: DatabaseEngine;
	host: string;
	port: string;
	database: string;
	username: string;
	password: string;
	sslMode: string;
	connectionTimeout: string;
	queryTimeout: string;
	readonly: boolean;
	maxRows: string;
	visibility: DatabaseConnection["visibility"];
	teamIds: string[];
}

interface DatabaseConnectionFormProps {
	connection?: DatabaseConnection;
}

function initialState(connection?: DatabaseConnection): FormState {
	return {
		name: connection?.name ?? "",
		description: connection?.description ?? "",
		engine: connection?.engine ?? "postgres",
		host: connection?.host ?? "",
		port: String(connection?.port ?? 5432),
		database: connection?.database ?? "",
		username: connection?.username ?? "",
		password: "",
		sslMode: connection?.sslMode ?? "",
		connectionTimeout: String(connection?.connectionTimeout ?? 10),
		queryTimeout: String(connection?.queryTimeout ?? 60),
		readonly: connection?.readonly ?? true,
		maxRows: String(connection?.maxRows ?? 1000),
		visibility: connection?.visibility ?? "workspace",
		teamIds: connection?.teamIds ?? [],
	};
}

function statusPanel(
	connection: DatabaseConnection,
	pollingError: string | null,
) {
	const status = STATUS_STYLES[connection.status];
	const StatusIcon = status.icon;

	return (
		<div
			role={connection.status === "error" || pollingError ? "alert" : "status"}
			className={`rounded-xl border p-4 ${status.className}`}
		>
			<div className="flex items-center gap-2 text-sm font-semibold">
				<StatusIcon
					className={`size-4 ${connection.status === "pending" ? "animate-spin" : ""}`}
				/>
				{status.label}
			</div>
			<p className="mt-1 text-sm opacity-80">
				{connection.status === "ready"
					? "DBHub has applied this source and exposed its allowed tools."
					: connection.status === "pending"
						? "The configuration is waiting to be applied by DBHub."
						: (connection.lastError ??
							"DBHub could not apply this configuration.")}
			</p>
			{pollingError ? (
				<p className="mt-2 text-sm font-medium">{pollingError}</p>
			) : null}
		</div>
	);
}

export function DatabaseConnectionForm({
	connection: initialConnection,
}: DatabaseConnectionFormProps) {
	const router = useRouter();
	const refreshMcpServers = useMcpServersStore(
		(state) => state.refreshMcpServers,
	);
	const [connection, setConnection] = useState(initialConnection);
	const [form, setForm] = useState(() => initialState(initialConnection));
	const [saving, setSaving] = useState(false);
	const [deleting, setDeleting] = useState(false);
	const [reconciling, setReconciling] = useState(false);
	const [pollingError, setPollingError] = useState<string | null>(null);
	const [pollRevision, setPollRevision] = useState(0);
	const isEditing = connection !== undefined;
	const connectionId = connection?.id;
	const connectionStatus = connection?.status;
	const invalidTeamSelection =
		form.visibility === "teams" && form.teamIds.length === 0;
	const mutating = saving || deleting || reconciling;

	useEffect(() => {
		if (!connectionId || connectionStatus !== "pending") return;
		let cancelled = false;
		let attempts = 0;
		let consecutiveFailures = 0;
		let timeout: number | undefined;

		const poll = async () => {
			attempts += 1;
			try {
				const nextConnection = await getDatabaseConnection(connectionId);
				if (cancelled) return;
				consecutiveFailures = 0;
				setConnection((current) =>
					current?.id === nextConnection.id ? nextConnection : current,
				);
				if (nextConnection.status !== "pending") {
					setPollingError(null);
					return;
				}
				if (attempts < 30) {
					setPollingError(null);
				}
			} catch {
				if (cancelled) return;
				consecutiveFailures += 1;
				if (consecutiveFailures >= 3) {
					setPollingError(
						"Could not refresh the DBHub status. Retrying automatically.",
					);
				}
			}

			if (attempts >= 30) {
				setPollingError(
					"DBHub is taking longer than expected. Status checks will continue.",
				);
			}
			timeout = window.setTimeout(() => {
				void poll();
			}, attempts >= 30 ? 30000 : 2000);
		};

		timeout = window.setTimeout(() => {
			void poll();
		}, 2000);
		return () => {
			cancelled = true;
			if (timeout !== undefined) {
				window.clearTimeout(timeout);
			}
		};
	}, [connectionId, connectionStatus, pollRevision]);

	const updateField = <Key extends keyof FormState>(
		key: Key,
		value: FormState[Key],
	) => {
		setForm((current) => ({ ...current, [key]: value }));
	};

	const handleEngineChange = (engine: DatabaseEngine) => {
		const defaultPort = ENGINE_OPTIONS.find(
			(option) => option.value === engine,
		)?.defaultPort;
		setForm((current) => ({
			...current,
			engine,
			port: String(defaultPort ?? current.port),
		}));
	};

	const handleReadonlyChange = (readonly: boolean) => {
		if (
			!readonly &&
			!window.confirm(
				"Allowing writes lets agents modify this database. Continue?",
			)
		) {
			return;
		}
		updateField("readonly", readonly);
	};

	const refreshServerList = () => {
		void refreshMcpServers().catch(() => {
			toast.warning("The MCP server list could not be refreshed.");
		});
	};

	const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		setSaving(true);
		try {
			const payload: DatabaseConnectionCreate = {
				name: form.name.trim(),
				description: form.description.trim() || null,
				engine: form.engine,
				host: form.host.trim(),
				port: Number(form.port),
				database: form.database.trim(),
				username: form.username.trim(),
				password: form.password,
				sslMode: form.sslMode.trim() || null,
				connectionTimeout: Number(form.connectionTimeout),
				queryTimeout: Number(form.queryTimeout),
				readonly: form.readonly,
				maxRows: Number(form.maxRows),
				visibility: form.visibility,
				teamIds: form.teamIds,
			};

			if (isEditing) {
				const update: DatabaseConnectionUpdate = {
					name: payload.name,
					description: payload.description,
					visibility: payload.visibility,
					teamIds: payload.teamIds,
					...(payload.password ? { password: payload.password } : {}),
				};
				if (payload.host !== connection.host) update.host = payload.host;
				if (payload.port !== connection.port) update.port = payload.port;
				if (payload.database !== connection.database) {
					update.database = payload.database;
				}
				if (payload.username !== connection.username) {
					update.username = payload.username;
				}
				if (payload.sslMode !== connection.sslMode) {
					update.sslMode = payload.sslMode;
				}
				if (payload.connectionTimeout !== connection.connectionTimeout) {
					update.connectionTimeout = payload.connectionTimeout;
				}
				if (payload.queryTimeout !== connection.queryTimeout) {
					update.queryTimeout = payload.queryTimeout;
				}
				if (payload.readonly !== connection.readonly) {
					update.readonly = payload.readonly;
				}
				if (payload.maxRows !== connection.maxRows) {
					update.maxRows = payload.maxRows;
				}

				const updated = await updateDatabaseConnection(connection.id, update);
				setConnection(updated);
				setForm((current) => ({ ...current, password: "" }));
				toast.success("Database connection updated");
				refreshServerList();
			} else {
				const created = await createDatabaseConnection(payload);
				toast.success(`${created.name} added to the workspace`);
				router.replace(`/mcp-servers/database/${created.id}`);
				refreshServerList();
			}
		} catch (error) {
			toast.error(
				getApiErrorMessage(error, "Could not save the database connection"),
			);
		} finally {
			setSaving(false);
		}
	};

	const handleReconcile = async () => {
		if (!connection) return;
		setReconciling(true);
		try {
			await reconcileDatabaseConnection(connection.id);
			setConnection({ ...connection, status: "pending", lastError: null });
			setPollingError(null);
			setPollRevision((current) => current + 1);
			toast.success("Reconciliation requested");
			router.refresh();
		} catch {
			toast.error("Could not request reconciliation");
		} finally {
			setReconciling(false);
		}
	};

	const performDelete = async (detachAgents: boolean) => {
		if (!connection) return;
		await deleteDatabaseConnection(connection.id, { detachAgents });
		toast.success("Database connection deleted");
		router.push("/mcp-servers");
		refreshServerList();
	};

	const handleDelete = async () => {
		if (
			!connection ||
			!window.confirm(
				"Delete this database connection? Its DBHub source and MCP server will also be removed.",
			)
		) {
			return;
		}
		setDeleting(true);
		try {
			await performDelete(false);
		} catch (error) {
			if (
				toApiError(error).status === 400 &&
				window.confirm(
					"This connection is attached to one or more agents. Detach it from those agents and delete it?",
				)
			) {
				try {
					await performDelete(true);
					return;
				} catch {
					toast.error("Could not delete the database connection");
				}
			} else {
				toast.error("Could not delete the database connection");
			}
		} finally {
			setDeleting(false);
		}
	};

	return (
		<div className="mx-auto w-full max-w-5xl px-5 py-8">
			<button
				type="button"
				onClick={() => {
					router.push("/mcp-servers");
				}}
				className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
			>
				<ArrowLeft className="size-4" />
				Back to MCP servers
			</button>

			<div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
				<div className="flex items-start gap-4">
					<div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
						<Database className="size-6" />
					</div>
					<div>
						<h1 className="text-2xl font-semibold tracking-tight">
							{isEditing ? connection.name : "Connect a database"}
						</h1>
						<p className="mt-1 text-sm text-muted-foreground">
							Managed through the workspace&apos;s private DBHub instance.
						</p>
					</div>
				</div>
				{connection ? (
					<div className="flex gap-2">
						{connection.status === "error" ? (
							<Button
								type="button"
								variant="outline"
								disabled={mutating}
								onClick={() => {
									void handleReconcile();
								}}
							>
								{reconciling ? (
									<Loader2 className="size-4 animate-spin" />
								) : (
									<RefreshCw className="size-4" />
								)}
								Retry
							</Button>
						) : null}
						<Button
							type="button"
							variant="destructive"
							disabled={mutating}
							onClick={() => {
								void handleDelete();
							}}
						>
							{deleting ? (
								<Loader2 className="size-4 animate-spin" />
							) : (
								<Trash2 className="size-4" />
							)}
							Delete
						</Button>
					</div>
				) : null}
			</div>

			{connection ? (
				<div className="mb-6">{statusPanel(connection, pollingError)}</div>
			) : null}

			<form onSubmit={(event) => void handleSubmit(event)}>
				<div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
					<div className="space-y-6">
						<section className="rounded-2xl border bg-card p-6 shadow-sm">
							<h2 className="mb-5 font-semibold">Connection</h2>
							<div className="grid gap-5 sm:grid-cols-2">
								<div className="space-y-2 sm:col-span-2">
									<Label htmlFor="database-name">Name</Label>
									<Input
										id="database-name"
										required
										value={form.name}
										onChange={(event) => {
											updateField("name", event.target.value);
										}}
										placeholder="Production analytics"
									/>
								</div>
								<div className="space-y-2 sm:col-span-2">
									<Label htmlFor="database-description">Description</Label>
									<Textarea
										id="database-description"
										value={form.description}
										onChange={(event) => {
											updateField("description", event.target.value);
										}}
										placeholder="What agents should use this database for"
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="database-engine">Engine</Label>
									<select
										id="database-engine"
										disabled={isEditing}
										value={form.engine}
										onChange={(event) => {
											handleEngineChange(event.target.value as DatabaseEngine);
										}}
										className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
									>
										{ENGINE_OPTIONS.map((option) => (
											<option key={option.value} value={option.value}>
												{option.label}
											</option>
										))}
									</select>
								</div>
								<div className="space-y-2">
									<Label htmlFor="database-host">Host</Label>
									<Input
										id="database-host"
										required
										value={form.host}
										onChange={(event) => {
											updateField("host", event.target.value);
										}}
										placeholder="db.internal.example"
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="database-port">Port</Label>
									<Input
										id="database-port"
										type="number"
										min={1}
										max={65535}
										required
										value={form.port}
										onChange={(event) => {
											updateField("port", event.target.value);
										}}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="database-database">Database</Label>
									<Input
										id="database-database"
										required
										value={form.database}
										onChange={(event) => {
											updateField("database", event.target.value);
										}}
										placeholder="analytics"
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="database-username">Username</Label>
									<Input
										id="database-username"
										required
										autoComplete="off"
										value={form.username}
										onChange={(event) => {
											updateField("username", event.target.value);
										}}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="database-password">
										Password {isEditing ? "(leave blank to keep)" : ""}
									</Label>
									<Input
										id="database-password"
										type="password"
										required={!isEditing}
										autoComplete="new-password"
										value={form.password}
										onChange={(event) => {
											updateField("password", event.target.value);
										}}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="database-ssl">SSL mode</Label>
									<Input
										id="database-ssl"
										value={form.sslMode}
										onChange={(event) => {
											updateField("sslMode", event.target.value);
										}}
										placeholder="require"
									/>
								</div>
							</div>
						</section>

						<section className="rounded-2xl border bg-card p-6 shadow-sm">
							<div className="mb-5 flex items-center gap-2">
								<ShieldCheck className="size-4 text-muted-foreground" />
								<h2 className="font-semibold">Query guardrails</h2>
							</div>
							<div className="space-y-5">
								<div className="flex items-center justify-between gap-4 rounded-xl border p-4">
									<div>
										<Label htmlFor="database-readonly">Read-only mode</Label>
										<p className="mt-1 text-sm text-muted-foreground">
											Blocks write statements before they reach the database.
										</p>
									</div>
									<Switch
										id="database-readonly"
										checked={form.readonly}
										onCheckedChange={handleReadonlyChange}
									/>
								</div>
								<div className="grid gap-5 sm:grid-cols-3">
									<div className="space-y-2">
										<Label htmlFor="database-max-rows">Maximum rows</Label>
										<Input
											id="database-max-rows"
											type="number"
											min={1}
											max={10000}
											required
											value={form.maxRows}
											onChange={(event) => {
												updateField("maxRows", event.target.value);
											}}
										/>
									</div>
									<div className="space-y-2">
										<Label htmlFor="database-connect-timeout">
											Connect timeout (s)
										</Label>
										<Input
											id="database-connect-timeout"
											type="number"
											min={1}
											max={300}
											required
											value={form.connectionTimeout}
											onChange={(event) => {
												updateField("connectionTimeout", event.target.value);
											}}
										/>
									</div>
									<div className="space-y-2">
										<Label htmlFor="database-query-timeout">
											Query timeout (s)
										</Label>
										<Input
											id="database-query-timeout"
											type="number"
											min={1}
											max={3600}
											required
											value={form.queryTimeout}
											onChange={(event) => {
												updateField("queryTimeout", event.target.value);
											}}
										/>
									</div>
								</div>
							</div>
						</section>
					</div>

					<div className="space-y-6">
						<section className="rounded-2xl border bg-card p-5 shadow-sm">
							<h2 className="mb-4 font-semibold">Access</h2>
							<VisibilityPicker
								visibility={form.visibility}
								teamIds={form.teamIds}
								onChange={(visibility, teamIds) => {
									setForm((current) => ({
										...current,
										visibility,
										teamIds,
									}));
								}}
							/>
						</section>

						<Button
							type="submit"
							className="w-full"
							disabled={mutating || invalidTeamSelection}
						>
							{saving ? (
								<Loader2 className="size-4 animate-spin" />
							) : (
								<Save className="size-4" />
							)}
							{isEditing ? "Save changes" : "Connect database"}
						</Button>
					</div>
				</div>
			</form>
		</div>
	);
}
