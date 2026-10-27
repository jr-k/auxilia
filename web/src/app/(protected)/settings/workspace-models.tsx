"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, RefreshCw, Search, Star, Trash2, Zap } from "lucide-react";
import { ModelSelectorLogo } from "@/components/ai-elements/model-selector";
import { HeaderButton } from "@/components/layout/subpage-header";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useQueryParamState } from "@/hooks/use-query-param-state";
import * as modelsApi from "@/lib/api/resources/models";
import { isApiError } from "@/lib/api/errors";
import { useModelsStore } from "@/stores/models-store";
import type {
	ManagedModel,
	ModelProviderConfig,
	WhitelistSyncResult,
} from "@/types/models";

const PROVIDER_LABELS = new Map<string, string>([
	["openai", "OpenAI"],
	["anthropic", "Anthropic"],
	["google", "Google"],
	["deepseek", "DeepSeek"],
	["xiaomi", "Xiaomi"],
	["openrouter", "OpenRouter"],
	["meta", "Meta"],
	["ollama", "Ollama"],
]);

function providerLabel(provider: string): string {
	return PROVIDER_LABELS.get(provider) ?? provider;
}

function apiErrorDetail(error: unknown): string | null {
	return isApiError(error) ? error.detail : null;
}

function syncSummary(result: WhitelistSyncResult): string {
	const changes = [
		result.added.length > 0 && `${result.added.length} added`,
		result.removed.length > 0 && `${result.removed.length} removed`,
	]
		.filter(Boolean)
		.join(", ");
	return `Catalog synced, ${changes || "no changes"} (${result.modelCount} models).`;
}

function orderManagedModels(models: ManagedModel[]): ManagedModel[] {
	return [...models].sort(
		(a, b) => Number(b.isEnabled) - Number(a.isEnabled),
	);
}

function preserveManagedModelOrder(
	current: ManagedModel[],
	incoming: ManagedModel[],
): ManagedModel[] {
	const byKey = new Map(
		incoming.map((model) => [`${model.provider}/${model.modelId}`, model]),
	);
	const ordered = current.flatMap((model) => {
		const updated = byKey.get(`${model.provider}/${model.modelId}`);
		if (!updated) return [];
		byKey.delete(`${model.provider}/${model.modelId}`);
		return [updated];
	});
	return [...ordered, ...byKey.values()];
}

/** Mono-caps chip on a model row (DEFAULT / capabilities / deprecation). */
function ModelBadge({
	tone,
	children,
}: {
	tone: "accent" | "neutral" | "destructive";
	children: React.ReactNode;
}) {
	const toneClass =
		tone === "accent"
			? "bg-petrol-tint text-petrol dark:bg-white/10 dark:text-panel-terminal"
			: tone === "destructive"
				? "bg-[#FBEFED] text-[#B04A3A] dark:bg-[#B04A3A]/10"
				: "bg-hover text-subtle dark:bg-white/10 dark:text-panel-body";
	return (
		<span
			className={`shrink-0 rounded-[4px] px-[7px] py-[2px] text-[9px] font-semibold ${toneClass}`}
		>
			{children}
		</span>
	);
}

function ModelRoleCard({
	icon,
	title,
	description,
	model,
	emptyText,
}: {
	icon: React.ReactNode;
	title: string;
	description: string;
	model?: ManagedModel;
	emptyText: string;
}) {
	return (
		<div className="min-w-0 overflow-hidden rounded-[10px] border border-hairline bg-card dark:border-white/10">
			<div className="flex items-center gap-2.5 border-b border-hairline bg-sidebar px-3.5 py-2.5 dark:border-white/10 dark:bg-white/[0.025]">
				<span className="flex size-7 shrink-0 items-center justify-center rounded-[7px] bg-hover text-ink dark:bg-white/10 dark:text-white">
					{icon}
				</span>
				<div className="min-w-0">
					<p className="text-[11.5px] font-semibold text-foreground">{title}</p>
					<p className="text-[10.5px] text-meta dark:text-panel-dim">
						{description}
					</p>
				</div>
			</div>
			<div className="flex min-h-[82px] items-center px-3.5 py-3">
				{model ? (
					<div className="flex min-w-0 items-center gap-3">
						<div className="flex size-10 shrink-0 items-center justify-center rounded-[9px] border border-hairline bg-canvas dark:border-white/10 dark:bg-white/[0.035]">
							<ModelSelectorLogo
								provider={model.chefSlug}
								className="size-5"
							/>
						</div>
						<div className="min-w-0">
							<div className="flex min-w-0 items-center gap-2">
								<p className="truncate text-[13px] font-semibold text-foreground">
									{model.displayName}
								</p>
								<span className="shrink-0 rounded-[4px] bg-hover px-1.5 py-0.5 text-[8.5px] font-semibold uppercase tracking-[0.04em] text-meta dark:bg-white/10 dark:text-panel-dim">
									{providerLabel(model.provider)}
								</span>
							</div>
							<p className="mt-0.5 truncate font-mono text-[10px] text-meta dark:text-panel-dim">
								{model.modelId}
							</p>
							<div className="mt-1.5 flex flex-wrap gap-1">
								{model.multimodal && (
									<ModelBadge tone="neutral">Multimodal</ModelBadge>
								)}
								{model.supportsStructuredOutput && (
									<ModelBadge tone="neutral">Structured</ModelBadge>
								)}
								<ModelBadge tone="neutral">Tools</ModelBadge>
							</div>
						</div>
					</div>
				) : (
					<div className="flex items-center gap-2 text-[11.5px] text-meta dark:text-panel-dim">
						<span className="size-1.5 rounded-full bg-faint" />
						{emptyText}
					</div>
				)}
			</div>
		</div>
	);
}

interface WorkspaceModelsProps {
	onForbidden: () => void;
	/** Reports usable models: enabled and backed by configured credentials. */
	onCountChange?: (count: number) => void;
	/** Refresh the remote catalog once before the initial list is loaded. */
	syncOnMount?: boolean;
	showSyncControl?: boolean;
}

export default function WorkspaceModels({
	onForbidden,
	onCountChange,
	syncOnMount = false,
	showSyncControl = true,
}: WorkspaceModelsProps) {
	const refreshModels = useModelsStore((state) => state.refreshModels);
	const [models, setModels] = useState<ManagedModel[]>([]);
	const [providers, setProviders] = useState<ModelProviderConfig[]>([]);
	const [searchQuery, setSearchQuery] = useState("");
	const [selectedProvider, setSelectedProvider] = useQueryParamState("provider");
	const [keyDrafts, setKeyDrafts] = useState<
		Partial<Record<string, string>>
	>({});
	const [ollamaUrlDraft, setOllamaUrlDraft] = useState("");
	const [pendingProviders, setPendingProviders] = useState<ReadonlySet<string>>(
		new Set(),
	);
	const [isLoading, setIsLoading] = useState(true);
	const [loadFailed, setLoadFailed] = useState(false);
	const [isSyncing, setIsSyncing] = useState(false);
	// Keys with a PUT in flight — a Set so overlapping toggles on different
	// rows don't re-enable each other's switch mid-request.
	const [pendingKeys, setPendingKeys] = useState<ReadonlySet<string>>(
		new Set(),
	);
	// Default changes rewrite every row's flag, so they are serialized: all
	// stars lock while one request is in flight.
	const [isDefaultUpdating, setIsDefaultUpdating] = useState(false);
	// Same serialization for the quick-model flag.
	const [isQuickUpdating, setIsQuickUpdating] = useState(false);
	const [status, setStatus] = useState<{
		kind: "info" | "error";
		text: string;
	} | null>(null);

	// Latest-callback ref: keeps loadManaged's identity stable (its consumer
	// is a mount effect) without freezing the first render's onForbidden.
	const onForbiddenRef = useRef(onForbidden);
	useEffect(() => {
		onForbiddenRef.current = onForbidden;
	}, [onForbidden]);

	const onCountChangeRef = useRef(onCountChange);
	useEffect(() => {
		onCountChangeRef.current = onCountChange;
	}, [onCountChange]);

	const hasSyncedOnMountRef = useRef(false);
	const hasLoadedModelsRef = useRef(false);
	useEffect(() => {
		if (!hasLoadedModelsRef.current) return;
		const configuredProviders = new Set(
			providers
				.filter((provider) => provider.isConfigured)
				.map((provider) => provider.name),
		);
		onCountChangeRef.current?.(
			models.filter(
				(model) =>
					model.isEnabled &&
					model.isAvailable &&
					model.supportsTools &&
					configuredProviders.has(model.provider),
			).length,
		);
	}, [models, providers]);

	const loadManaged = useCallback(async () => {
		setIsLoading(true);
		setLoadFailed(false);
		if (syncOnMount && !hasSyncedOnMountRef.current) {
			hasSyncedOnMountRef.current = true;
			setIsSyncing(true);
			try {
				await modelsApi.syncWhitelist();
			} catch (error: unknown) {
				if (isApiError(error) && error.status === 403) {
					onForbiddenRef.current();
					setIsLoading(false);
					return;
				}
				setStatus({
					kind: "error",
					text:
						apiErrorDetail(error) ??
						"Catalog sync failed. The existing catalog is shown instead.",
				});
			} finally {
				setIsSyncing(false);
			}
		}
		try {
			const [managed, providerConfigs] = await Promise.all([
				modelsApi.listManagedModels(),
				modelsApi.listProviderConfigs(),
			]);
			setModels(orderManagedModels(managed));
			setProviders(providerConfigs);
			const ollama = providerConfigs.find(
				(provider) => provider.name === "ollama",
			);
			setOllamaUrlDraft((current) => current || ollama?.baseUrl || "");
			const providerFromUrl = new URL(
				window.location.href,
			).searchParams.get("provider");
			if (
				!providerFromUrl ||
				!providerConfigs.some(
					(provider) => provider.name === providerFromUrl,
				)
			) {
				const fallback =
					providerConfigs.find((provider) => provider.isConfigured)?.name ??
					providerConfigs[0]?.name;
				if (fallback) setSelectedProvider(fallback);
			}
			// Only model state originating from a successful fetch reports a count;
			// the initial empty array must not show a misleading "Models 0".
			hasLoadedModelsRef.current = true;
		} catch (error: unknown) {
			if (isApiError(error) && error.status === 403) {
				onForbiddenRef.current();
			} else {
				console.error("Error fetching workspace models:", error);
				// Distinct from an empty catalog — "no providers configured"
				// would send the admin chasing the wrong problem.
				setLoadFailed(true);
			}
		} finally {
			setIsLoading(false);
		}
	}, [setSelectedProvider, syncOnMount]);

	useEffect(() => {
		const timeoutId = window.setTimeout(() => {
			void loadManaged();
		}, 0);
		return () => {
			window.clearTimeout(timeoutId);
		};
	}, [loadManaged]);

	// The order is frozen from the last load: toggling a row updates it in place
	// instead of making it jump between the enabled and disabled sections.
	const providerGroups = useMemo(() => {
		const query = searchQuery.trim().toLocaleLowerCase();
		return providers
			.map((provider) => {
				const allProviderModels = models.filter(
					(model) => model.provider === provider.name,
				);
				const providerModels = allProviderModels.filter(
					(model) =>
						!query ||
						model.displayName.toLocaleLowerCase().includes(query) ||
						model.modelId.toLocaleLowerCase().includes(query),
				);
				return {
					provider,
					models: providerModels,
					enabledCount: allProviderModels.filter((model) => model.isEnabled)
						.length,
					totalCount: allProviderModels.length,
				};
			});
	}, [models, providers, searchQuery]);

	const selectedGroup =
		providerGroups.find(
			({ provider }) => provider.name === selectedProvider,
		) ??
		providerGroups.find(({ provider }) => provider.isConfigured) ??
		providerGroups[0];

	const updateProvider = (updated: ModelProviderConfig) => {
		setProviders((current) =>
			current.map((provider) =>
				provider.name === updated.name ? updated : provider,
			),
		);
	};

	const handleProviderKeySave = async (provider: ModelProviderConfig) => {
		const apiKey = keyDrafts[provider.name]?.trim();
		if (!apiKey) return;
		setPendingProviders((current) => new Set(current).add(provider.name));
		setStatus(null);
		try {
			updateProvider(
				await modelsApi.setProviderApiKey(provider.name, apiKey),
			);
			setKeyDrafts((current) => ({ ...current, [provider.name]: "" }));
			setStatus({
				kind: "info",
				text: `${providerLabel(provider.name)} API key saved.`,
			});
			await refreshModels().catch(() => {});
		} catch (error: unknown) {
			if (isApiError(error) && error.status === 403) {
				onForbidden();
			} else {
				setStatus({
					kind: "error",
					text:
						apiErrorDetail(error) ??
						`Could not save the ${providerLabel(provider.name)} API key.`,
				});
			}
		} finally {
			setPendingProviders((current) => {
				const next = new Set(current);
				next.delete(provider.name);
				return next;
			});
		}
	};

	const handleProviderKeyDelete = async (provider: ModelProviderConfig) => {
		setPendingProviders((current) => new Set(current).add(provider.name));
		setStatus(null);
		try {
			const updated = await modelsApi.deleteProviderApiKey(provider.name);
			updateProvider(updated);
			if (!updated.isConfigured) {
				setModels((current) =>
					current.map((model) =>
						model.provider === provider.name
							? { ...model, isDefault: false }
							: model,
					),
				);
			}
			setKeyDrafts((current) => ({ ...current, [provider.name]: "" }));
			setStatus({
				kind: "info",
				text:
					updated.source === "environment"
						? `${providerLabel(provider.name)} now uses the deployment environment key.`
						: updated.source === "adc"
							? `${providerLabel(provider.name)} now uses Google Application Default Credentials.`
						: `${providerLabel(provider.name)} API key removed.`,
			});
			await refreshModels().catch(() => {});
		} catch (error: unknown) {
			if (isApiError(error) && error.status === 403) {
				onForbidden();
			} else {
				setStatus({
					kind: "error",
					text:
						apiErrorDetail(error) ??
						`Could not remove the ${providerLabel(provider.name)} API key.`,
				});
			}
		} finally {
			setPendingProviders((current) => {
				const next = new Set(current);
				next.delete(provider.name);
				return next;
			});
		}
	};

	const refreshManagedModels = async () => {
		const managed = await modelsApi.listManagedModels();
		setModels((current) => preserveManagedModelOrder(current, managed));
		await refreshModels().catch(() => {});
	};

	const handleOllamaConnect = async () => {
		const baseUrl = ollamaUrlDraft.trim();
		if (!baseUrl) return;
		setPendingProviders((current) => new Set(current).add("ollama"));
		setStatus(null);
		try {
			const result = await modelsApi.connectOllama(baseUrl);
			updateProvider(result.config);
			setOllamaUrlDraft(result.config.baseUrl ?? baseUrl);
			await refreshManagedModels();
			setStatus({
				kind: "info",
				text: `Ollama connected. ${result.discoveredCount} models discovered, ${result.availableCount} support tools.`,
			});
		} catch (error: unknown) {
			if (isApiError(error) && error.status === 403) {
				onForbidden();
			} else {
				setStatus({
					kind: "error",
					text:
						apiErrorDetail(error) ??
						"Could not connect to Ollama. Check that the URL is reachable from the backend.",
				});
			}
		} finally {
			setPendingProviders((current) => {
				const next = new Set(current);
				next.delete("ollama");
				return next;
			});
		}
	};

	const handleOllamaDiscover = async () => {
		setPendingProviders((current) => new Set(current).add("ollama"));
		setStatus(null);
		try {
			const result = await modelsApi.discoverOllama();
			updateProvider(result.config);
			await refreshManagedModels();
			setStatus({
				kind: "info",
				text: `Ollama refreshed. ${result.discoveredCount} models found, ${result.availableCount} support tools.`,
			});
		} catch (error: unknown) {
			if (isApiError(error) && error.status === 403) {
				onForbidden();
			} else {
				setStatus({
					kind: "error",
					text:
						apiErrorDetail(error) ??
						"Could not refresh models from Ollama.",
				});
			}
		} finally {
			setPendingProviders((current) => {
				const next = new Set(current);
				next.delete("ollama");
				return next;
			});
		}
	};

	const handleOllamaDisconnect = async () => {
		setPendingProviders((current) => new Set(current).add("ollama"));
		setStatus(null);
		try {
			const updated = await modelsApi.disconnectOllama();
			updateProvider(updated);
			setOllamaUrlDraft("");
			setModels((current) =>
				current.filter((model) => model.provider !== "ollama"),
			);
			await refreshModels().catch(() => {});
			setStatus({ kind: "info", text: "Ollama disconnected." });
		} catch (error: unknown) {
			if (isApiError(error) && error.status === 403) {
				onForbidden();
			} else {
				setStatus({
					kind: "error",
					text: apiErrorDetail(error) ?? "Could not disconnect Ollama.",
				});
			}
		} finally {
			setPendingProviders((current) => {
				const next = new Set(current);
				next.delete("ollama");
				return next;
			});
		}
	};

	const handleToggle = async (model: ManagedModel, isEnabled: boolean) => {
		const key = `${model.provider}/${model.modelId}`;
		setPendingKeys((prev) => new Set(prev).add(key));
		setStatus(null);
		// Optimistic flip; reverted on failure. Disabling the default also
		// clears its flag (the backend auto-unsets — back to automatic).
		setModels((prev) =>
			prev.map((m) =>
				m.provider === model.provider && m.modelId === model.modelId
					? {
							...m,
							isEnabled,
							isDefault: isEnabled ? m.isDefault : false,
							isQuick: isEnabled ? m.isQuick : false,
						}
					: m,
			),
		);
		try {
			await modelsApi.setModelEnabled(model.provider, model.modelId, isEnabled);
			// Every open model picker reflects the change without a reload.
			await refreshModels().catch(() => {});
		} catch (error: unknown) {
			// A connection can fail after the backend has committed the change.
			// Reconcile before reporting an error so the UI reflects persisted state.
			let persisted = false;
			try {
				const managed = await modelsApi.listManagedModels();
				persisted =
					managed.find(
						(item) =>
							item.provider === model.provider &&
							item.modelId === model.modelId,
					)?.isEnabled === isEnabled;
				setModels((current) => preserveManagedModelOrder(current, managed));
			} catch {
				setModels((prev) =>
					prev.map((m) =>
						m.provider === model.provider && m.modelId === model.modelId
							? {
									...m,
									isEnabled: !isEnabled,
									isDefault: model.isDefault,
									isQuick: model.isQuick,
								}
							: m,
					),
				);
			}
			if (persisted) {
				await refreshModels().catch(() => {});
				return;
			}
			if (isApiError(error) && error.status === 403) {
				onForbidden();
			} else {
				setStatus({
					kind: "error",
					text:
						apiErrorDetail(error) ??
						`Could not update ${model.displayName}. Please retry.`,
				});
			}
		} finally {
			setPendingKeys((prev) => {
				const next = new Set(prev);
				next.delete(key);
				return next;
			});
		}
	};

	const handleSetDefault = async (model: ManagedModel) => {
		const key = `${model.provider}/${model.modelId}`;
		// Clicking the current default's star unsets it (back to automatic).
		const makeDefault = !model.isDefault;
		setIsDefaultUpdating(true);
		setPendingKeys((prev) => new Set(prev).add(key));
		setStatus(null);
		// Optimistic: exactly one default at a time — flag the target, clear
		// the rest.
		setModels((prev) =>
			prev.map((m) => ({
				...m,
				isDefault:
					makeDefault &&
					m.provider === model.provider &&
					m.modelId === model.modelId,
			})),
		);
		try {
			if (makeDefault) {
				await modelsApi.setDefaultModel(model.provider, model.modelId);
			} else {
				await modelsApi.clearDefaultModel();
			}
			// Every open model picker preselects the new default without a reload.
			await refreshModels().catch(() => {});
		} catch (error: unknown) {
			// Refetch instead of reverting from a snapshot: the persisted state
			// is the only reliable source after a failure.
			await loadManaged();
			if (isApiError(error) && error.status === 403) {
				onForbidden();
			} else {
				setStatus({
					kind: "error",
					text:
						apiErrorDetail(error) ??
						`Could not update the default model. Please retry.`,
				});
			}
		} finally {
			setIsDefaultUpdating(false);
			setPendingKeys((prev) => {
				const next = new Set(prev);
				next.delete(key);
				return next;
			});
		}
	};

	const handleSetQuick = async (model: ManagedModel) => {
		const key = `${model.provider}/${model.modelId}`;
		// Clicking the current quick model's bolt unsets it.
		const makeQuick = !model.isQuick;
		setIsQuickUpdating(true);
		setPendingKeys((prev) => new Set(prev).add(key));
		setStatus(null);
		// Optimistic: exactly one quick model at a time.
		setModels((prev) =>
			prev.map((m) => ({
				...m,
				isQuick:
					makeQuick &&
					m.provider === model.provider &&
					m.modelId === model.modelId,
			})),
		);
		try {
			if (makeQuick) {
				await modelsApi.setQuickModel(model.provider, model.modelId);
			} else {
				await modelsApi.clearQuickModel();
			}
		} catch (error: unknown) {
			await loadManaged();
			if (isApiError(error) && error.status === 403) {
				onForbidden();
			} else {
				setStatus({
					kind: "error",
					text:
						apiErrorDetail(error) ??
						`Could not update the quick model. Please retry.`,
				});
			}
		} finally {
			setIsQuickUpdating(false);
			setPendingKeys((prev) => {
				const next = new Set(prev);
				next.delete(key);
				return next;
			});
		}
	};

	const handleSync = async () => {
		setIsSyncing(true);
		setStatus(null);
		let summary: string;
		try {
			summary = syncSummary(await modelsApi.syncWhitelist());
		} catch (error: unknown) {
			if (isApiError(error) && error.status === 403) {
				onForbidden();
			} else {
				setStatus({
					kind: "error",
					text: apiErrorDetail(error) ?? "Catalog sync failed. Please retry.",
				});
			}
			setIsSyncing(false);
			return;
		}
		// The sync itself succeeded — a refetch hiccup must not report it as
		// failed (the backend has already applied the new catalog).
		try {
			const managed = await modelsApi.listManagedModels();
			setModels((current) => preserveManagedModelOrder(current, managed));
			setStatus({ kind: "info", text: summary });
		} catch {
			setStatus({
				kind: "info",
				text: `${summary} The list below could not be refreshed, reload the page.`,
			});
		} finally {
			setIsSyncing(false);
		}
		await refreshModels().catch(() => {});
	};

	const defaultModel = models.find((model) => model.isDefault);
	const quickModel = models.find((model) => model.isQuick);

	return (
		<div>
			<div className="mb-1.5 flex items-baseline gap-2.5">
				<span className="text-[10.5px] font-semibold text-subtle dark:text-panel-dim">
					Workspace models
				</span>
				<span className="text-[10.5px] text-meta dark:text-panel-dim">
					admin
				</span>
				<span className="flex-1" />
				{showSyncControl && (
					<HeaderButton
						accent
						className="gap-1.5 px-3.5 py-[7px] text-[12.5px]"
						disabled={isSyncing}
						onClick={() => {
							void handleSync();
						}}
					>
						<RefreshCw
							className={
								isSyncing ? "size-[13px] animate-spin" : "size-[13px]"
							}
						/>
						Sync catalog
					</HeaderButton>
				)}
			</div>
			<p className="mb-3.5 max-w-[640px] text-[13px] leading-[1.55] text-subtle text-pretty dark:text-panel-body">
				Choose which models members can use in chats and triggers. New catalog
				models start disabled.
			</p>
			{status && (
				<p
					className={`mb-3 text-[13px] font-medium ${
						status.kind === "error"
							? "text-destructive"
							: "text-subtle dark:text-panel-body"
					}`}
				>
					{status.text}
				</p>
			)}
			<div className="mb-3 grid gap-3 sm:grid-cols-2">
				<ModelRoleCard
					icon={
						<Star
							className="size-[14px] fill-current"
							aria-hidden="true"
						/>
					}
					title="Default model"
					description="New chats and Slack"
					model={defaultModel}
					emptyText="Automatic — first available model"
				/>
				<ModelRoleCard
					icon={
						<Zap
							className="size-[14px] fill-current"
							aria-hidden="true"
						/>
					}
					title="Quick model"
					description="Fast intermediate actions"
					model={quickModel}
					emptyText="Conversation model at minimal effort"
				/>
			</div>
			<div className="relative mb-3">
				<Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" />
				<Input
					type="search"
					value={searchQuery}
					onChange={(event) => {
						setSearchQuery(event.target.value);
					}}
					placeholder="Search models by name"
					aria-label="Search models by name"
					className="h-10 pl-9"
				/>
			</div>

			<div className="overflow-hidden rounded-[10px] border border-border bg-card dark:border-white/10">
				{isLoading ? (
					<div className="flex items-center justify-center gap-2 px-4 py-12 text-[14px] font-medium text-faint dark:text-muted-foreground">
						<Loader2 className="size-4 animate-spin" aria-hidden="true" />
						<span>Loading…</span>
					</div>
				) : loadFailed ? (
					<div className="px-4 py-12 text-center">
						<p className="mb-3 text-[14px] font-medium text-faint dark:text-muted-foreground">
							Could not load the workspace models.
						</p>
						<HeaderButton
							className="mx-auto"
							onClick={() => {
								void loadManaged();
							}}
						>
							Retry
						</HeaderButton>
					</div>
				) : providerGroups.length === 0 ? (
					<div className="px-4 py-12 text-center text-[14px] font-medium text-faint dark:text-muted-foreground">
						No model providers are available.
					</div>
				) : (
					<div className="grid min-h-[430px] md:grid-cols-[190px_minmax(0,1fr)]">
						<nav
							aria-label="Model providers"
							className="flex gap-1 overflow-x-auto border-b border-hairline bg-sidebar p-2 md:flex-col md:overflow-x-visible md:border-r md:border-b-0 md:p-2.5 dark:border-white/5 dark:bg-white/[0.025]"
						>
							{providerGroups.map(
								({ provider, enabledCount, totalCount }) => {
									const isSelected =
										provider.name === selectedGroup?.provider.name;
									return (
										<button
											key={provider.name}
											type="button"
											aria-current={isSelected ? "page" : undefined}
											onClick={() => {
												setSelectedProvider(provider.name);
											}}
											className={`group flex min-w-[165px] cursor-pointer items-center gap-2.5 rounded-[8px] px-3 py-2.5 text-left transition-colors md:min-w-0 ${
												isSelected
													? "bg-card shadow-[0_1px_2px_rgba(0,0,0,0.05)] ring-1 ring-border dark:bg-white/[0.08] dark:ring-white/10"
													: "hover:bg-hover dark:hover:bg-white/[0.05]"
											}`}
										>
											<span
												className={`flex size-7 shrink-0 items-center justify-center rounded-[7px] border ${
													isSelected
														? "border-border bg-background dark:border-white/10 dark:bg-black/15"
														: "border-transparent bg-card dark:bg-white/[0.05]"
												}`}
											>
												<ModelSelectorLogo
													provider={provider.name}
													className="size-4"
												/>
											</span>
											<span className="min-w-0 flex-1">
												<span className="flex items-center gap-1.5">
													<span className="truncate text-[12.5px] font-semibold text-foreground">
														{providerLabel(provider.name)}
													</span>
													<span
														className={`size-1.5 shrink-0 rounded-full ${
															provider.isConfigured
																? "bg-emerald-500"
																: "bg-faint"
														}`}
													/>
												</span>
												<span className="mt-0.5 block font-mono text-[9.5px] text-meta dark:text-panel-dim">
													{enabledCount}/{totalCount} enabled
												</span>
											</span>
										</button>
									);
								},
							)}
						</nav>

						{selectedGroup && (
							<div className="min-w-0">
								<div className="border-b border-hairline px-4 py-4 dark:border-white/5 sm:px-5">
									<div className="mb-3 flex items-start justify-between gap-4">
										<div className="min-w-0">
											<div className="flex items-center gap-2">
												<h2 className="text-[15px] font-semibold text-foreground">
													{providerLabel(selectedGroup.provider.name)}
												</h2>
												<span
													className={`size-1.5 rounded-full ${
														selectedGroup.provider.isConfigured
															? "bg-emerald-500"
															: "bg-faint"
													}`}
												/>
											</div>
											<p className="mt-0.5 text-[11px] text-meta dark:text-panel-dim">
												{selectedGroup.provider.configurationType ===
												"base_url"
													? selectedGroup.provider.baseUrl
														? `Connected to ${selectedGroup.provider.baseUrl}`
														: "Ollama endpoint not configured"
													: selectedGroup.provider.source === "database"
														? `API key configured${
																selectedGroup.provider.last4
																	? `, ending in ${selectedGroup.provider.last4}`
																	: ""
															}`
														: selectedGroup.provider.source === "environment"
															? "Using deployment environment key"
															: selectedGroup.provider.source === "adc"
																? "Using Google Application Default Credentials"
																: "API key not configured"}
											</p>
										</div>
										<span className="shrink-0 pt-0.5 text-[10.5px] text-meta dark:text-panel-dim">
											<span className="font-mono">
												{selectedGroup.enabledCount}/{selectedGroup.totalCount}
											</span>{" "}
											enabled
										</span>
									</div>
									{selectedGroup.provider.configurationType ===
									"base_url" ? (
										<div>
											<form
												className="flex flex-col gap-2 sm:flex-row sm:items-center"
												onSubmit={(event) => {
													event.preventDefault();
													void handleOllamaConnect();
												}}
											>
												<Input
													type="url"
													value={ollamaUrlDraft}
													onChange={(event) => {
														setOllamaUrlDraft(event.target.value);
													}}
													placeholder="http://localhost:11434"
													aria-label="Ollama base URL"
													disabled={pendingProviders.has("ollama")}
													className="h-9 flex-1 font-mono text-[12px]"
												/>
												<div className="flex items-center gap-2">
													<HeaderButton
														type="submit"
														accent
														disabled={
															pendingProviders.has("ollama") ||
															!ollamaUrlDraft.trim()
														}
													>
														{pendingProviders.has("ollama")
															? "Connecting…"
															: selectedGroup.provider.isConfigured
																? "Connect & refresh"
																: "Connect & discover"}
													</HeaderButton>
													{selectedGroup.provider.isConfigured && (
														<>
															<HeaderButton
																type="button"
																disabled={pendingProviders.has("ollama")}
																onClick={() => {
																	void handleOllamaDiscover();
																}}
															>
																<RefreshCw className="size-3.5" />
																Refresh
															</HeaderButton>
															<button
																type="button"
																aria-label="Disconnect Ollama"
																title="Disconnect Ollama"
																disabled={pendingProviders.has("ollama")}
																onClick={() => {
																	void handleOllamaDisconnect();
																}}
																className="flex size-8 cursor-pointer items-center justify-center rounded-[7px] text-faint transition-colors hover:bg-destructive/10 hover:text-destructive disabled:cursor-default disabled:opacity-50"
															>
																<Trash2 className="size-3.5" />
															</button>
														</>
													)}
												</div>
											</form>
											<p className="mt-2 text-[10.5px] leading-relaxed text-meta dark:text-panel-dim">
												Use{" "}
												<span className="font-mono">localhost:11434</span>{" "}
												when the backend runs on the host,{" "}
												<span className="font-mono">
													host.docker.internal:11434
												</span>{" "}
												from Docker, a service name on a shared network, or
												any remote URL reachable by the backend.
											</p>
										</div>
									) : (
										<form
											className="flex flex-col gap-2 sm:flex-row sm:items-center"
											onSubmit={(event) => {
												event.preventDefault();
												void handleProviderKeySave(selectedGroup.provider);
											}}
										>
											<Input
												type="password"
												autoComplete="new-password"
												value={keyDrafts[selectedGroup.provider.name] ?? ""}
												onChange={(event) => {
													setKeyDrafts((current) => ({
														...current,
														[selectedGroup.provider.name]:
															event.target.value,
													}));
												}}
												placeholder={
													selectedGroup.provider.isConfigured
														? "Enter a new API key to replace the current key"
														: "Enter API key"
												}
												aria-label={`${providerLabel(selectedGroup.provider.name)} API key`}
												disabled={pendingProviders.has(
													selectedGroup.provider.name,
												)}
												className="h-9 flex-1 font-mono text-[12px]"
											/>
											<div className="flex items-center gap-2">
												<HeaderButton
													type="submit"
													accent
													disabled={
														pendingProviders.has(
															selectedGroup.provider.name,
														) ||
														!keyDrafts[
															selectedGroup.provider.name
														]?.trim()
													}
												>
													{pendingProviders.has(
														selectedGroup.provider.name,
													)
														? "Saving…"
														: selectedGroup.provider.source === "database"
															? "Replace key"
															: "Save key"}
												</HeaderButton>
												{selectedGroup.provider.source === "database" && (
													<button
														type="button"
														aria-label={`Remove ${providerLabel(selectedGroup.provider.name)} API key`}
														title="Remove stored API key"
														disabled={pendingProviders.has(
															selectedGroup.provider.name,
														)}
														onClick={() => {
															void handleProviderKeyDelete(
																selectedGroup.provider,
															);
														}}
														className="flex size-8 cursor-pointer items-center justify-center rounded-[7px] text-faint transition-colors hover:bg-destructive/10 hover:text-destructive disabled:cursor-default disabled:opacity-50"
													>
														<Trash2 className="size-3.5" />
													</button>
												)}
											</div>
										</form>
									)}
								</div>

								{selectedGroup.models.length === 0 ? (
									<div className="px-4 py-12 text-center text-[13px] text-faint">
										{searchQuery.trim()
											? "No models match your search for this provider."
											: "No models available for this provider."}
									</div>
								) : (
									selectedGroup.models.map((model) => {
										const key = `${model.provider}/${model.modelId}`;
										return (
											<div
												key={key}
												className="flex items-center gap-3 border-b border-hairline px-4 py-3 transition-colors last:border-b-0 hover:bg-sidebar sm:px-5 dark:border-white/5 dark:hover:bg-white/5"
											>
												<ModelSelectorLogo
													provider={model.chefSlug}
													className={
														model.isEnabled
															? "size-4 shrink-0"
															: "size-4 shrink-0 opacity-45"
													}
												/>
												<div className="min-w-0 flex-1">
													<div className="flex flex-wrap items-center gap-2">
														<span
															className={`text-[13.5px] font-semibold ${
																model.isEnabled
																	? "text-foreground"
																	: "text-meta dark:text-panel-dim"
															}`}
														>
															{model.displayName}
														</span>
														{model.isDefault && (
															<ModelBadge tone="accent">Default</ModelBadge>
														)}
														{model.isQuick && (
															<ModelBadge tone="accent">Quick</ModelBadge>
														)}
														{model.deprecated && (
															<ModelBadge tone="destructive">
																{model.provider === "ollama"
																	? "Not found on Ollama"
																	: "No longer supported"}
															</ModelBadge>
														)}
														{!model.supportsTools &&
															model.isAvailable && (
																<ModelBadge tone="destructive">
																	No tool support
																</ModelBadge>
															)}
														{model.multimodal && (
															<ModelBadge tone="neutral">Multimodal</ModelBadge>
														)}
														{model.supportsStructuredOutput && (
															<ModelBadge tone="neutral">
																Structured output
															</ModelBadge>
														)}
													</div>
													<span
														className={`mt-0.5 block truncate font-mono text-[10.5px] ${
															model.isEnabled
																? "text-meta dark:text-panel-dim"
																: "text-faint dark:text-panel-dim/70"
														}`}
													>
														{model.modelId}
													</span>
												</div>
												<button
													type="button"
													aria-label={
														model.isQuick
															? `Unset ${model.displayName} as the quick model`
															: `Set ${model.displayName} as the quick model`
													}
													title={
														model.isQuick
															? "Unset as quick model"
															: "Set as quick model (fast intermediate steps)"
													}
													disabled={
														pendingKeys.has(key) ||
														isSyncing ||
														isQuickUpdating ||
														!model.isEnabled ||
														!selectedGroup.provider.isConfigured ||
														!model.supportsTools ||
														model.deprecated
													}
													onClick={() => {
														void handleSetQuick(model);
													}}
													className="flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-[7px] transition-colors hover:bg-hover disabled:cursor-default disabled:opacity-50 disabled:hover:bg-transparent dark:hover:bg-white/10"
												>
													<Zap
														className={
															model.isQuick
																? "size-[15px] fill-current text-ink dark:text-white"
																: "size-[15px] text-faint"
														}
													/>
												</button>
												<button
													type="button"
													aria-label={
														model.isDefault
															? `Unset ${model.displayName} as the workspace default`
															: `Set ${model.displayName} as the workspace default`
													}
													title={
														model.isDefault
															? "Unset as default (back to automatic)"
															: "Set as workspace default"
													}
													disabled={
														pendingKeys.has(key) ||
														isSyncing ||
														isDefaultUpdating ||
														!model.isEnabled ||
														!selectedGroup.provider.isConfigured ||
														!model.supportsTools ||
														model.deprecated
													}
													onClick={() => {
														void handleSetDefault(model);
													}}
													className="flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-[7px] transition-colors hover:bg-hover disabled:cursor-default disabled:opacity-50 disabled:hover:bg-transparent dark:hover:bg-white/10"
												>
													<Star
														className={
															model.isDefault
																? "size-[15px] fill-current text-ink dark:text-white"
																: "size-[15px] text-faint"
														}
													/>
												</button>
												<Switch
													checked={model.isEnabled}
													aria-label={`Enable ${model.displayName} (${model.modelId})`}
													disabled={
														pendingKeys.has(key) ||
														isSyncing ||
														(!selectedGroup.provider.isConfigured &&
															!model.isEnabled) ||
														(!model.supportsTools && !model.isEnabled) ||
														(model.deprecated && !model.isEnabled)
													}
													onCheckedChange={(checked) => {
														void handleToggle(model, checked);
													}}
													className="cursor-pointer data-[state=checked]:bg-petrol"
												/>
											</div>
										);
									})
								)}
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
}
