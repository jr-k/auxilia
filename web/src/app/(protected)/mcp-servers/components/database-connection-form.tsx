"use client";

import {
	AlertCircle,
	CheckCircle2,
	Loader2,
	RefreshCw,
	ShieldCheck,
	Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { EditorSection } from "@/components/editor/editor-section";
import {
	HeaderButton,
	HeaderPrimaryButton,
	SubpageHeader,
} from "@/components/layout/subpage-header";
import { useConfirmDialog } from "@/components/providers/dialog-provider";
import { GroupPicker } from "@/components/ui/group-picker";
import { ImageUpload } from "@/components/ui/image-upload";
import { Switch } from "@/components/ui/switch";
import { VisibilityPicker } from "@/components/ui/visibility-picker";
import { getApiErrorMessage, toApiError } from "@/lib/api/errors";
import { groupOptions } from "@/lib/groups";
import {
	createDatabaseConnection,
	deleteDatabaseConnection,
	getDatabaseConnection,
	reconcileDatabaseConnection,
	updateDatabaseConnection,
} from "@/lib/api/resources/database-connections";
import * as mcpServersApi from "@/lib/api/resources/mcp-servers";
import { useMcpServersStore } from "@/stores/mcp-servers-store";
import type {
	DatabaseConnection,
	DatabaseConnectionCreate,
	DatabaseEngine,
	DatabaseConnectionUpdate,
} from "@/types/database-connections";
import { ServerIconTile } from "./server-icon-tile";

const ENGINE_OPTIONS: Array<{
	value: DatabaseEngine;
	label: string;
	defaultPort: number;
	iconUrl: string;
}> = [
	{
		value: "postgres",
		label: "PostgreSQL",
		defaultPort: 5432,
		iconUrl:
			"https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/postgresql/postgresql-original.svg",
	},
	{
		value: "mysql",
		label: "MySQL",
		defaultPort: 3306,
		iconUrl:
			"https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/mysql/mysql-original.svg",
	},
	{
		value: "mariadb",
		label: "MariaDB",
		defaultPort: 3306,
		iconUrl:
			"https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/mariadb/mariadb-original.svg",
	},
	{
		value: "sqlserver",
		label: "SQL Server",
		defaultPort: 1433,
		iconUrl:
			"https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/microsoftsqlserver/microsoftsqlserver-original.svg",
	},
	{
		value: "oracle",
		label: "Oracle",
		defaultPort: 1521,
		iconUrl:
			"https://cdn.jsdelivr.net/gh/devicons/devicon@v2.17.0/icons/oracle/oracle-original.svg",
	},
];

const LABEL_CLASS =
	"text-[11px] font-semibold text-label dark:text-muted-foreground";
const INPUT_CLASS =
	"w-full rounded-lg border border-input bg-card px-3 py-[9px] text-[13.5px] font-medium text-foreground outline-none transition-[border-color,box-shadow] placeholder:text-meta dark:placeholder:text-panel-dim focus:border-petrol focus:shadow-[0_0_0_3px_rgba(22,96,110,0.10)] disabled:cursor-not-allowed disabled:opacity-60";
const MONO_INPUT_CLASS = `${INPUT_CLASS} font-mono text-[12.5px] font-normal`;

const STATUS_STYLES = {
	pending: {
		label: "Pending",
		icon: RefreshCw,
		className:
			"bg-warning-bg text-warning dark:bg-warning/10",
	},
	ready: {
		label: "Ready",
		icon: CheckCircle2,
		className:
			"bg-success-bg text-success dark:bg-success/10",
	},
	error: {
		label: "Error",
		icon: AlertCircle,
		className:
			"bg-destructive/10 text-destructive",
	},
} as const;

interface FormState {
	name: string;
	description: string;
	group: string;
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
		group: connection?.group ?? "",
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
			className={`rounded-[10px] px-4 py-3.5 ${status.className}`}
		>
			<div className="flex items-center gap-2 text-[13px] font-semibold">
				<StatusIcon
					className={`size-4 ${connection.status === "pending" ? "animate-spin" : ""}`}
				/>
				{status.label}
			</div>
			<p className="mt-1 pl-6 text-[12.5px] leading-5 opacity-80">
				{connection.status === "ready"
					? "The connection is ready and its tools are available to agents."
					: connection.status === "pending"
						? "The database connection is being configured."
						: (connection.lastError ??
							"The database connection could not be configured.")}
			</p>
			{pollingError ? (
				<p className="mt-2 pl-6 text-[12.5px] font-medium">{pollingError}</p>
			) : null}
		</div>
	);
}

export function DatabaseConnectionForm({
	connection: initialConnection,
}: DatabaseConnectionFormProps) {
	const router = useRouter();
	const confirmDialog = useConfirmDialog();
	const refreshMcpServers = useMcpServersStore(
		(state) => state.refreshMcpServers,
	);
	const fetchMcpServers = useMcpServersStore(
		(state) => state.fetchMcpServers,
	);
	const mcpServers = useMcpServersStore((state) => state.mcpServers);
	const [connection, setConnection] = useState(initialConnection);
	const [form, setForm] = useState(() => initialState(initialConnection));
	const [saving, setSaving] = useState(false);
	const [deleting, setDeleting] = useState(false);
	const [reconciling, setReconciling] = useState(false);
	const [imageFile, setImageFile] = useState<File | null>(null);
	const [removeImage, setRemoveImage] = useState(false);
	const [pollingError, setPollingError] = useState<string | null>(null);
	const [pollRevision, setPollRevision] = useState(0);
	const isEditing = connection !== undefined;
	const connectionId = connection?.id;
	const connectionStatus = connection?.status;
	const invalidTeamSelection =
		form.visibility === "teams" && form.teamIds.length === 0;
	const mutating = saving || deleting || reconciling;
	const selectedEngine = ENGINE_OPTIONS.find(
		(option) => option.value === form.engine,
	);
	const engineIconUrl = selectedEngine?.iconUrl;

	useEffect(() => {
		void fetchMcpServers().catch(() => undefined);
	}, [fetchMcpServers]);

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
				const stillApplying =
					nextConnection.status === "error" &&
					nextConnection.lastError ===
						"The database connection could not be configured" &&
					attempts < 5;
				if (!stillApplying) {
					setConnection((current) =>
						current?.id === nextConnection.id ? nextConnection : current,
					);
				}
				if (nextConnection.status !== "pending" && !stillApplying) {
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
						"Could not refresh the connection status. Retrying automatically.",
					);
				}
			}

			if (attempts >= 30) {
				setPollingError(
					"The connection is taking longer than expected. Status checks will continue.",
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
		setForm((current) => {
			const previousDefaultPort = ENGINE_OPTIONS.find(
				(option) => option.value === current.engine,
			)?.defaultPort;
			const nextDefaultPort = ENGINE_OPTIONS.find(
				(option) => option.value === engine,
			)?.defaultPort;
			return {
				...current,
				engine,
				port:
					current.port === String(previousDefaultPort)
						? String(nextDefaultPort ?? current.port)
						: current.port,
			};
		});
	};

	const handleReadonlyChange = async (readonly: boolean) => {
		if (
			!readonly &&
			!(await confirmDialog({
				title: "Enable database writes?",
				description:
					"Agents using this connection will be able to run INSERT, UPDATE, DELETE, and other write statements against the database.",
				confirmLabel: "Enable writes",
				destructive: true,
			}))
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

	const buildPayload = (): DatabaseConnectionCreate => ({
		name: form.name.trim(),
		description: form.description.trim() || null,
		group: form.group.trim() || null,
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
	});

	const saveExistingConnection = async (
		current: DatabaseConnection,
		payload: DatabaseConnectionCreate,
	) => {
		const databaseChanged =
			Boolean(payload.password) ||
			payload.engine !== current.engine ||
			payload.host !== current.host ||
			payload.port !== current.port ||
			payload.database !== current.database ||
			payload.username !== current.username ||
			payload.sslMode !== current.sslMode ||
			payload.connectionTimeout !== current.connectionTimeout ||
			payload.queryTimeout !== current.queryTimeout ||
			payload.readonly !== current.readonly ||
			payload.maxRows !== current.maxRows;
		const update: DatabaseConnectionUpdate = {
			name: payload.name,
			description: payload.description,
			group: payload.group,
			visibility: payload.visibility,
			teamIds: payload.teamIds,
			...(payload.password ? { password: payload.password } : {}),
		};
		if (payload.engine !== current.engine) update.engine = payload.engine;
		if (payload.host !== current.host) update.host = payload.host;
		if (payload.port !== current.port) update.port = payload.port;
		if (payload.database !== current.database) {
			update.database = payload.database;
		}
		if (payload.username !== current.username) {
			update.username = payload.username;
		}
		if (payload.sslMode !== current.sslMode) {
			update.sslMode = payload.sslMode;
		}
		if (payload.connectionTimeout !== current.connectionTimeout) {
			update.connectionTimeout = payload.connectionTimeout;
		}
		if (payload.queryTimeout !== current.queryTimeout) {
			update.queryTimeout = payload.queryTimeout;
		}
		if (payload.readonly !== current.readonly) {
			update.readonly = payload.readonly;
		}
		if (payload.maxRows !== current.maxRows) {
			update.maxRows = payload.maxRows;
		}

		let updated = await updateDatabaseConnection(current.id, update);
		if (imageFile) {
			const imageRevision = await mcpServersApi.uploadMcpServerImage(
				current.mcpServerId,
				imageFile,
			);
			updated = { ...updated, imageRevision };
		} else if (removeImage && current.imageRevision) {
			await mcpServersApi.deleteMcpServerImage(current.mcpServerId);
			updated = { ...updated, imageRevision: null };
		}
		setConnection(updated);
		setForm((draft) => ({ ...draft, password: "" }));
		setImageFile(null);
		setRemoveImage(false);
		refreshServerList();
		return { updated, databaseChanged };
	};

	const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		setSaving(true);
		try {
			const payload = buildPayload();

			if (isEditing) {
				await saveExistingConnection(connection, payload);
				toast.success("Database connection updated");
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
			const { updated, databaseChanged } = await saveExistingConnection(
				connection,
				buildPayload(),
			);
			if (!databaseChanged) {
				await reconcileDatabaseConnection(connection.id);
			}
			setConnection({ ...updated, status: "pending", lastError: null });
			setPollingError(null);
			setPollRevision((current) => current + 1);
			toast.success(
				databaseChanged
					? "Changes saved; retrying connection"
					: "Reconciliation requested",
			);
			router.refresh();
		} catch (error) {
			toast.error(
				getApiErrorMessage(error, "Could not save and retry the connection"),
			);
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
		if (!connection) return;
		if (
			!(await confirmDialog({
				title: `Delete “${connection.name}”?`,
				description:
					"The database connection and its managed MCP server will be removed permanently.",
				confirmLabel: "Delete connection",
				destructive: true,
			}))
		)
			return;
		setDeleting(true);
		try {
			await performDelete(false);
		} catch (error) {
			if (
				toApiError(error).status === 400 &&
				(await confirmDialog({
					title: "Detach agents and delete?",
					description:
						"This connection is still attached to one or more agents. It must be detached before the database connection can be deleted.",
					confirmLabel: "Detach and delete",
					destructive: true,
				}))
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

	const canSave = Boolean(
		form.name.trim() &&
			form.host.trim() &&
			form.port &&
			form.database.trim() &&
			form.username.trim() &&
			(isEditing || form.password) &&
			form.maxRows &&
			form.connectionTimeout &&
			form.queryTimeout &&
			!invalidTeamSelection,
	);
	return (
		<div className="flex h-svh min-w-0 flex-1 flex-col bg-background animate-in fade-in duration-300">
			<SubpageHeader
				trail={[
					{ label: "workspace" },
					{ label: "mcp-servers", href: "/mcp-servers" },
					{ label: isEditing ? connection.name : "new" },
				]}
			>
				<HeaderButton
					disabled={mutating}
					onClick={() => {
						router.push("/mcp-servers");
					}}
				>
					Cancel
				</HeaderButton>
				{connection?.status === "error" ? (
					<HeaderButton
						accent
						disabled={mutating || !canSave}
						onClick={() => {
							void handleReconcile();
						}}
					>
						{reconciling ? (
							<Loader2 className="size-3.5 animate-spin" />
						) : (
							<RefreshCw className="size-3.5" />
						)}
						Retry
					</HeaderButton>
				) : null}
				<HeaderPrimaryButton
					type="submit"
					form="database-connection-form"
					disabled={mutating || !canSave}
				>
					{saving
						? "Saving…"
						: isEditing
							? "Save changes"
							: "Connect database"}
				</HeaderPrimaryButton>
			</SubpageHeader>

			<form
				id="database-connection-form"
				className="flex min-h-0 flex-1 flex-col overflow-y-auto md:flex-row md:overflow-hidden"
				onSubmit={(event) => void handleSubmit(event)}
			>
				<div className="flex min-w-0 shrink-0 flex-col border-b border-border bg-background p-7 md:min-h-0 md:flex-[1.05] md:shrink md:overflow-y-auto md:border-b-0 md:border-r [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
					<div className="flex items-start gap-4">
						<ServerIconTile
							iconUrl={engineIconUrl}
							serverId={connection?.mcpServerId}
							imageRevision={
								connection && !removeImage
									? connection.imageRevision
									: undefined
							}
							name={form.name || "Database"}
							size={52}
						/>
						<div className="min-w-0 flex-1">
							<h1 className="font-display text-[26px] font-bold tracking-[-0.03em] text-foreground">
								{isEditing ? connection.name : "Connect a database"}
							</h1>
							<p className="mt-1.5 max-w-2xl text-[13.5px] leading-[1.6] text-body dark:text-panel-body">
								A private database connection exposed to agents as a managed
								MCP server.
							</p>
						</div>
					</div>

					{connection ? (
						<div className="mt-6">
							{statusPanel(connection, pollingError)}
						</div>
					) : null}

					<div className="mt-8 flex min-w-0 flex-col gap-7">
								<EditorSection label="Connection name">
									<input
										id="database-name"
										required
										autoFocus={!isEditing}
										value={form.name}
										onChange={(event) => {
											updateField("name", event.target.value);
										}}
										placeholder="Production analytics"
										className="w-full rounded-[10px] border border-input bg-card px-3.5 py-3 text-[15px] font-semibold leading-[1.5] text-foreground outline-none transition-[border-color,box-shadow] placeholder:font-medium placeholder:text-meta dark:placeholder:text-panel-dim focus:border-petrol focus:shadow-[0_0_0_3px_rgba(22,96,110,0.10)]"
									/>
								</EditorSection>

								<EditorSection label="Description" hint="Optional">
									<textarea
										id="database-description"
										rows={3}
										value={form.description}
										onChange={(event) => {
											updateField("description", event.target.value);
										}}
										placeholder="What agents should use this database for"
										className={`${INPUT_CLASS} resize-none leading-[1.55]`}
									/>
								</EditorSection>

								{connection ? (
									<EditorSection label="Logo">
										<ImageUpload
											currentUrl={
												connection.imageRevision && !removeImage
													? mcpServersApi.mcpServerImageUrl(
															connection.mcpServerId,
															connection.imageRevision,
														)
													: engineIconUrl
											}
											file={imageFile}
											onFileChange={(file) => {
												setImageFile(file);
												if (file) setRemoveImage(false);
											}}
											onRemove={() => {
												if (imageFile) {
													setImageFile(null);
													return;
												}
												if (connection.imageRevision) {
													setRemoveImage(true);
												}
											}}
											label="Database logo"
											disabled={mutating}
											removable={
												Boolean(connection.imageRevision) && !removeImage
											}
											className="rounded-[12px] border border-hairline bg-sidebar p-3 dark:border-white/5"
										/>
									</EditorSection>
								) : null}

								<GroupPicker
									value={form.group}
									groups={groupOptions(mcpServers)}
									onChange={(group) => {
										updateField("group", group);
									}}
								/>

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

								<EditorSection label="Query guardrails">
									<div className="overflow-hidden rounded-[10px] border border-border bg-card">
										<div className="flex items-center justify-between gap-4 p-5">
											<div className="flex min-w-0 gap-3">
												<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-petrol-tint text-petrol dark:bg-white/10 dark:text-panel-terminal">
													<ShieldCheck className="size-[18px]" />
												</div>
												<div>
													<label
														htmlFor="database-readonly"
														className="text-[13px] font-semibold text-foreground"
													>
														Read-only mode
													</label>
													<p className="mt-0.5 text-[11.5px] leading-5 text-meta dark:text-panel-dim">
														Block write statements before they reach the
														database.
													</p>
												</div>
											</div>
											<Switch
												id="database-readonly"
												checked={form.readonly}
												onCheckedChange={(readonly) => {
													void handleReadonlyChange(readonly);
												}}
											/>
										</div>
										<div className="grid gap-[18px] border-t border-hairline bg-sidebar/60 p-5 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3 dark:border-white/5 dark:bg-white/3">
											<div className="flex flex-col gap-[7px]">
												<label
													htmlFor="database-max-rows"
													className={LABEL_CLASS}
												>
													Maximum rows
												</label>
												<input
													id="database-max-rows"
													type="number"
													min={1}
													max={10000}
													required
													value={form.maxRows}
													onChange={(event) => {
														updateField("maxRows", event.target.value);
													}}
													className={MONO_INPUT_CLASS}
												/>
											</div>
											<div className="flex flex-col gap-[7px]">
												<label
													htmlFor="database-connect-timeout"
													className={LABEL_CLASS}
												>
													Connect (s)
												</label>
												<input
													id="database-connect-timeout"
													type="number"
													min={1}
													max={300}
													required
													value={form.connectionTimeout}
													onChange={(event) => {
														updateField(
															"connectionTimeout",
															event.target.value,
														);
													}}
													className={MONO_INPUT_CLASS}
												/>
											</div>
											<div className="flex flex-col gap-[7px]">
												<label
													htmlFor="database-query-timeout"
													className={LABEL_CLASS}
												>
													Query (s)
												</label>
												<input
													id="database-query-timeout"
													type="number"
													min={1}
													max={3600}
													required
													value={form.queryTimeout}
													onChange={(event) => {
														updateField("queryTimeout", event.target.value);
													}}
													className={MONO_INPUT_CLASS}
												/>
											</div>
										</div>
									</div>
								</EditorSection>

								{connection ? (
									<div className="flex items-center justify-between gap-4 border-t border-hairline pt-5 dark:border-white/5">
										<div>
											<p className="text-[12.5px] font-semibold text-foreground">
												Delete connection
											</p>
											<p className="mt-0.5 text-[11.5px] leading-5 text-meta dark:text-panel-dim">
												Removes the managed MCP server too.
											</p>
										</div>
										<button
											type="button"
											disabled={mutating}
											onClick={() => {
												void handleDelete();
											}}
											className="flex cursor-pointer items-center gap-1.5 rounded-[7px] border border-destructive/25 bg-card px-3.5 py-2 text-[12.5px] font-semibold text-destructive transition-colors hover:bg-destructive/5 disabled:cursor-not-allowed disabled:opacity-50"
										>
											{deleting ? (
												<Loader2 className="size-3.5 animate-spin" />
											) : (
												<Trash2 className="size-3.5" />
											)}
											Delete
										</button>
									</div>
								) : null}
							</div>
				</div>

				<div className="flex min-w-0 shrink-0 flex-col gap-7 bg-sidebar p-7 md:min-h-0 md:flex-1 md:shrink md:overflow-y-auto dark:bg-white/[0.02] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
								<EditorSection label="Connection details">
									<div className="grid gap-[18px] rounded-[10px] border border-border bg-card p-5 sm:grid-cols-2">
										<div className="flex flex-col gap-[7px]">
											<label htmlFor="database-engine" className={LABEL_CLASS}>
												Engine
											</label>
											<select
												id="database-engine"
												value={form.engine}
												onChange={(event) => {
													handleEngineChange(
														event.target.value as DatabaseEngine,
													);
												}}
												className={INPUT_CLASS}
											>
												{ENGINE_OPTIONS.map((option) => (
													<option key={option.value} value={option.value}>
														{option.label}
													</option>
												))}
											</select>
										</div>
										<div className="flex flex-col gap-[7px]">
											<label htmlFor="database-port" className={LABEL_CLASS}>
												Port
											</label>
											<input
												id="database-port"
												type="number"
												min={1}
												max={65535}
												required
												value={form.port}
												placeholder={String(selectedEngine?.defaultPort ?? "")}
												onChange={(event) => {
													updateField("port", event.target.value);
												}}
												className={MONO_INPUT_CLASS}
											/>
										</div>
										<div className="flex flex-col gap-[7px] sm:col-span-2">
											<label htmlFor="database-host" className={LABEL_CLASS}>
												Host
											</label>
											<input
												id="database-host"
												required
												value={form.host}
												onChange={(event) => {
													updateField("host", event.target.value);
												}}
												placeholder="db.internal.example"
												className={MONO_INPUT_CLASS}
											/>
											<span className="text-[11px] leading-5 text-meta dark:text-panel-dim">
												Must be reachable from the Auxilia deployment.
											</span>
										</div>
										<div className="flex flex-col gap-[7px]">
											<label htmlFor="database-database" className={LABEL_CLASS}>
												Database
											</label>
											<input
												id="database-database"
												required
												value={form.database}
												onChange={(event) => {
													updateField("database", event.target.value);
												}}
												placeholder="analytics"
												className={MONO_INPUT_CLASS}
											/>
										</div>
										<div className="flex flex-col gap-[7px]">
											<label htmlFor="database-ssl" className={LABEL_CLASS}>
												SSL mode
											</label>
											<input
												id="database-ssl"
												value={form.sslMode}
												onChange={(event) => {
													updateField("sslMode", event.target.value);
												}}
												placeholder="require"
												className={MONO_INPUT_CLASS}
											/>
										</div>
									</div>
								</EditorSection>

								<EditorSection label="Credentials">
									<div className="flex flex-col gap-[18px] rounded-[10px] border border-border bg-card p-5">
										<div className="flex flex-col gap-[7px]">
											<label htmlFor="database-username" className={LABEL_CLASS}>
												Username
											</label>
											<input
												id="database-username"
												required
												autoComplete="off"
												value={form.username}
												onChange={(event) => {
													updateField("username", event.target.value);
												}}
												className={MONO_INPUT_CLASS}
											/>
										</div>
										<div className="flex flex-col gap-[7px]">
											<label htmlFor="database-password" className={LABEL_CLASS}>
												Password
												{isEditing ? (
													<span className="font-normal text-meta dark:text-panel-dim">
														{" "}
														leave blank to keep
													</span>
												) : null}
											</label>
											<input
												id="database-password"
												type="password"
												required={!isEditing}
												autoComplete="new-password"
												value={form.password}
												onChange={(event) => {
													updateField("password", event.target.value);
												}}
												className={MONO_INPUT_CLASS}
											/>
										</div>
										<p className="text-[11.5px] leading-5 text-meta dark:text-panel-dim">
											Credentials are encrypted at rest and never shown again.
										</p>
									</div>
								</EditorSection>
				</div>
			</form>
		</div>
	);
}
