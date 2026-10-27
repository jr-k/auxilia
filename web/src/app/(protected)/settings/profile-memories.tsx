"use client";

import {
	ArrowDown,
	ArrowUp,
	Brain,
	ChevronDown,
	Clock3,
	Database,
	FolderOpen,
	Pencil,
	Plus,
	Search,
	Sparkles,
	Trash2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useConfirmDialog } from "@/components/providers/dialog-provider";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
	Dialog,
	DialogButton,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { getApiErrorMessage } from "@/lib/api/errors";
import * as memoriesApi from "@/lib/api/resources/memories";
import type {
	Memory,
	MemoryCategoryGroup,
	MemoryLibrary,
} from "@/types/memories";

const inputClass =
	"w-full rounded-[8px] border border-input bg-card px-3 py-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-meta focus:border-petrol";
const iconButtonClass =
	"flex size-7 cursor-pointer items-center justify-center rounded-[7px] text-meta transition-colors hover:bg-hover hover:text-foreground disabled:cursor-default disabled:opacity-35 dark:hover:bg-white/5";

type CategoryDraft = { id: string | null; name: string } | null;
type MemoryDraft = {
	id: string | null;
	categoryId: string;
	title: string;
	content: string;
} | null;

const emptyLibrary: MemoryLibrary = { categories: [], total: 0 };

function updatedLabel(value: string): string {
	return new Intl.DateTimeFormat("en-US", {
		day: "numeric",
		month: "short",
		year: "numeric",
	}).format(new Date(value));
}

function MemoryEditor({
	draft,
	categories,
	busy,
	onOpenChange,
	onChange,
	onSave,
}: {
	draft: MemoryDraft;
	categories: MemoryCategoryGroup[];
	busy: boolean;
	onOpenChange: (open: boolean) => void;
	onChange: (draft: MemoryDraft) => void;
	onSave: () => void;
}) {
	if (!draft) return null;
	const editing = draft.id !== null;
	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!busy) onOpenChange(open);
			}}
		>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>
						{editing ? "Edit memory" : "New memory"}
					</DialogTitle>
					<DialogDescription>
						A short, durable fact your assistants can reuse when relevant.
					</DialogDescription>
				</DialogHeader>
				<div className="grid gap-4">
					<label>
						<span className="mb-1.5 block text-[10px] font-semibold text-subtle">
							Category
						</span>
						<select
							value={draft.categoryId}
							disabled={busy}
							onChange={(event) => {
								onChange({ ...draft, categoryId: event.target.value });
							}}
							className={inputClass}
						>
							{categories.map((category) => (
								<option key={category.id} value={category.id}>
									{category.name}
								</option>
							))}
						</select>
					</label>
					<label>
						<span className="mb-1.5 block text-[10px] font-semibold text-subtle">
							Title
						</span>
						<input
							value={draft.title}
							disabled={busy}
							maxLength={200}
							placeholder="Home address"
							onChange={(event) => {
								onChange({ ...draft, title: event.target.value });
							}}
							className={inputClass}
						/>
					</label>
					<label>
						<span className="mb-1.5 block text-[10px] font-semibold text-subtle">
							Information
						</span>
						<textarea
							value={draft.content}
							disabled={busy}
							maxLength={10_000}
							rows={5}
							placeholder="7 Galilee Street, Villeurbanne"
							onChange={(event) => {
								onChange({ ...draft, content: event.target.value });
							}}
							className={`${inputClass} resize-y leading-5`}
						/>
					</label>
				</div>
				<DialogFooter>
					<DialogButton
						variant="outline"
						disabled={busy}
						onClick={() => {
							onOpenChange(false);
						}}
					>
						Cancel
					</DialogButton>
					<DialogButton
						disabled={
							busy ||
							!draft.categoryId ||
							!draft.title.trim() ||
							!draft.content.trim()
						}
						onClick={onSave}
					>
						{busy ? "Saving…" : editing ? "Save" : "Add"}
					</DialogButton>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}

export default function ProfileMemories() {
	const confirmDialog = useConfirmDialog();
	const [library, setLibrary] = useState<MemoryLibrary>(emptyLibrary);
	const [autoCapture, setAutoCapture] = useState(false);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [query, setQuery] = useState("");
	const [openCategories, setOpenCategories] = useState<Set<string>>(new Set());
	const [categoryDraft, setCategoryDraft] = useState<CategoryDraft>(null);
	const [memoryDraft, setMemoryDraft] = useState<MemoryDraft>(null);
	const [saving, setSaving] = useState(false);
	const [preferenceSaving, setPreferenceSaving] = useState(false);
	const [preferenceLoaded, setPreferenceLoaded] = useState(false);
	const [reorderSaving, setReorderSaving] = useState(false);
	const loadGeneration = useRef(0);

	const load = async () => {
		const generation = ++loadGeneration.current;
		setError(null);
		const [libraryResult, preferencesResult] = await Promise.allSettled([
			memoriesApi.getMemoryLibrary(),
			memoriesApi.getMemoryPreferences(),
		]);
		if (generation !== loadGeneration.current) return;

		if (libraryResult.status === "fulfilled") {
			const nextLibrary = libraryResult.value;
			setLibrary(nextLibrary);
			setOpenCategories((current) => {
				if (current.size > 0) return current;
				return new Set(nextLibrary.categories.map((category) => category.id));
			});
		}
		if (preferencesResult.status === "fulfilled") {
			setAutoCapture(preferencesResult.value.autoCaptureEnabled);
			setPreferenceLoaded(true);
		} else {
			setPreferenceLoaded(false);
		}
		if (
			libraryResult.status === "rejected" ||
			preferencesResult.status === "rejected"
		) {
			const reason =
				libraryResult.status === "rejected"
					? libraryResult.reason
					: preferencesResult.status === "rejected"
						? preferencesResult.reason
						: null;
			setError(
				getApiErrorMessage(
					reason,
					"Your memories could not be fully loaded right now.",
				),
			);
		}
		setLoading(false);
	};

	useEffect(() => {
		void load();
	}, []);

	const filteredCategories = useMemo(() => {
		const term = query.trim().toLocaleLowerCase("en-US");
		if (!term) return library.categories;
		return library.categories
			.map((category) => {
				if (category.name.toLocaleLowerCase("en-US").includes(term)) {
					return category;
				}
				return {
					...category,
					memories: category.memories.filter((memory) =>
						[memory.title, memory.content, memory.key].some((value) =>
							value.toLocaleLowerCase("en-US").includes(term),
						),
					),
				};
			})
			.filter((category) => category.memories.length > 0);
	}, [library.categories, query]);

	const saveCategory = async () => {
		if (saving || !categoryDraft?.name.trim()) return;
		setSaving(true);
		try {
			if (categoryDraft.id) {
				await memoriesApi.updateMemoryCategory(
					categoryDraft.id,
					categoryDraft.name.trim(),
				);
			} else {
				await memoriesApi.createMemoryCategory(categoryDraft.name.trim());
			}
			setCategoryDraft(null);
			await load();
		} catch (caught: unknown) {
			toast.error(
				getApiErrorMessage(caught, "The category could not be saved."),
			);
		} finally {
			setSaving(false);
		}
	};

	const saveMemory = async () => {
		if (
			saving ||
			!memoryDraft?.categoryId ||
			!memoryDraft.title.trim() ||
			!memoryDraft.content.trim()
		) {
			return;
		}
		setSaving(true);
		try {
			const payload = {
				categoryId: memoryDraft.categoryId,
				title: memoryDraft.title.trim(),
				content: memoryDraft.content.trim(),
			};
			if (memoryDraft.id) {
				await memoriesApi.updateMemory(memoryDraft.id, payload);
			} else {
				await memoriesApi.createMemory(payload);
			}
			setMemoryDraft(null);
			await load();
		} catch (caught: unknown) {
			toast.error(
				getApiErrorMessage(caught, "The memory could not be saved."),
			);
		} finally {
			setSaving(false);
		}
	};

	const deleteCategory = async (category: MemoryCategoryGroup) => {
		const confirmed = await confirmDialog({
			title: `Delete “${category.name}”?`,
			description:
				category.memoryCount > 0
					? `This category and its ${category.memoryCount} ${category.memoryCount === 1 ? "memory" : "memories"} will be permanently deleted.`
					: "This empty category will be permanently deleted.",
			confirmLabel: "Delete category",
			destructive: true,
		});
		if (!confirmed) return;
		try {
			await memoriesApi.deleteMemoryCategory(category.id);
			await load();
		} catch (caught: unknown) {
			toast.error(
				getApiErrorMessage(caught, "The category could not be deleted."),
			);
		}
	};

	const deleteMemory = async (memory: Memory) => {
		const confirmed = await confirmDialog({
			title: `Delete “${memory.title}”?`,
			description: "This memory will no longer be available in your conversations.",
			confirmLabel: "Delete memory",
			destructive: true,
		});
		if (!confirmed) return;
		try {
			await memoriesApi.deleteMemory(memory.id);
			await load();
		} catch (caught: unknown) {
			toast.error(
				getApiErrorMessage(caught, "The memory could not be deleted."),
			);
		}
	};

	const moveCategory = async (categoryId: string, direction: -1 | 1) => {
		if (reorderSaving) return;
		const current = library.categories;
		const index = current.findIndex((category) => category.id === categoryId);
		const target = index + direction;
		if (index < 0 || target < 0 || target >= current.length) return;
		const reordered = [...current];
		[reordered[index], reordered[target]] = [
			reordered[target],
			reordered[index],
		];
		setLibrary({
			...library,
			categories: reordered.map((category, position) => ({
				...category,
				position,
			})),
		});
		setReorderSaving(true);
		try {
			await memoriesApi.reorderMemoryCategories(
				reordered.map((category) => category.id),
			);
			await load();
		} catch (caught: unknown) {
			setLibrary(library);
			toast.error(
				getApiErrorMessage(
					caught,
					"The category order could not be saved.",
				),
			);
		} finally {
			setReorderSaving(false);
		}
	};

	const updateAutoCapture = async (enabled: boolean) => {
		if (preferenceSaving || !preferenceLoaded) return;
		const previous = autoCapture;
		setAutoCapture(enabled);
		setPreferenceSaving(true);
		try {
			const preferences = await memoriesApi.updateMemoryPreferences(enabled);
			setAutoCapture(preferences.autoCaptureEnabled);
		} catch (caught: unknown) {
			setAutoCapture(previous);
			toast.error(
				getApiErrorMessage(
					caught,
					"The preference could not be saved.",
				),
			);
		} finally {
			setPreferenceSaving(false);
		}
	};

	return (
		<div className="flex flex-col gap-4">
			<div className="mb-1 flex items-start justify-between gap-4">
				<div>
					<span className="text-[10.5px] font-semibold text-subtle dark:text-panel-dim">
						Memories
					</span>
					<p className="mt-1.5 max-w-[620px] text-[13px] leading-[1.55] text-subtle dark:text-panel-body">
						Organize personal information your assistants can recall across
						conversations.
					</p>
				</div>
				<span className="flex h-8 shrink-0 items-center rounded-full border border-border bg-card px-3 font-mono text-[10.5px] text-meta">
					{library.total} {library.total === 1 ? "memory" : "memories"}
				</span>
			</div>

			<section className="overflow-hidden rounded-[12px] border border-border bg-card">
				<div className="flex items-start gap-3 border-b border-border bg-[linear-gradient(135deg,rgba(22,95,104,0.08),transparent_65%)] p-5 dark:bg-[linear-gradient(135deg,rgba(102,192,199,0.09),transparent_65%)]">
					<span className="flex size-9 shrink-0 items-center justify-center rounded-[9px] border border-petrol/20 bg-white/80 text-petrol dark:bg-white/5 dark:text-panel-terminal">
						<Sparkles className="size-4" />
					</span>
					<div className="min-w-0 flex-1">
						<p className="text-[13px] font-semibold text-foreground">
							Automatic capture
						</p>
						<p className="mt-1 max-w-[590px] text-[12px] leading-5 text-subtle dark:text-panel-body">
							Allow conversations to automatically remember information about
							you. Content resembling passwords, authentication secrets, or
							payment-card numbers is rejected.
						</p>
					</div>
					<Switch
						checked={autoCapture}
						disabled={loading || !preferenceLoaded || preferenceSaving}
						onCheckedChange={(checked) => {
							void updateAutoCapture(checked);
						}}
						aria-label="Allow automatic memory capture"
						className="mt-1"
					/>
				</div>
				<div className="flex items-center gap-2 px-5 py-3 text-[11px] text-meta">
					<Brain className="size-3.5 text-petrol dark:text-panel-terminal" />
					Memories are account-wide and can always be edited here.
				</div>
			</section>

			<section className="rounded-[12px] border border-border bg-card p-4 sm:p-5">
				<div className="flex flex-col gap-3 sm:flex-row sm:items-center">
					<label className="relative min-w-0 flex-1">
						<Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-meta" />
						<input
							value={query}
							aria-label="Search your memories"
							onChange={(event) => {
								setQuery(event.target.value);
							}}
							placeholder="Search your memories…"
							className={`${inputClass} pl-9`}
						/>
					</label>
					<button
						type="button"
						onClick={() => {
							setCategoryDraft({ id: null, name: "" });
						}}
						className="inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-[7px] border border-input px-3.5 py-2.5 text-[12.5px] font-semibold text-foreground transition-colors hover:border-border-hover"
					>
						<Plus className="size-3.5" />
						Category
					</button>
					<button
						type="button"
						disabled={library.categories.length === 0}
						onClick={() => {
							const first = library.categories[0];
							if (!first) return;
							setMemoryDraft({
								id: null,
								categoryId: first.id,
								title: "",
								content: "",
							});
						}}
						className="inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-[7px] bg-primary px-3.5 py-2.5 text-[12.5px] font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-default disabled:opacity-40"
					>
						<Plus className="size-3.5" />
						Memory
					</button>
				</div>

				{error && (
					<div className="mt-4 rounded-[9px] border border-destructive/20 bg-destructive/5 px-4 py-3 text-[12.5px] text-destructive">
						{error}
						<button
							type="button"
							onClick={() => {
								setLoading(true);
								void load();
							}}
							className="ml-2 cursor-pointer font-semibold underline underline-offset-2"
						>
							Retry
						</button>
					</div>
				)}

				<div className="mt-4 flex flex-col gap-3">
					{loading ? (
						<>
							<div className="h-24 animate-pulse rounded-[10px] bg-hover" />
							<div className="h-24 animate-pulse rounded-[10px] bg-hover" />
						</>
					) : filteredCategories.length === 0 ? (
						<div className="flex flex-col items-center rounded-[10px] border border-dashed border-input px-6 py-12 text-center">
							<span className="flex size-10 items-center justify-center rounded-full bg-hover text-meta dark:bg-white/5">
								<Database className="size-4" />
							</span>
							<p className="mt-3 text-[13px] font-semibold text-foreground">
								{query ? "No memories found" : "No memories saved"}
							</p>
							<p className="mt-1 max-w-sm text-[12px] leading-5 text-subtle">
								{query
									? "Try another search term."
									: "Create a category first, then add information you want to recall later."}
							</p>
						</div>
					) : (
						filteredCategories.map((category, index) => {
							const open = openCategories.has(category.id);
							return (
								<Collapsible
									key={category.id}
									open={open}
									onOpenChange={(nextOpen) => {
										setOpenCategories((current) => {
											const next = new Set(current);
											if (nextOpen) next.add(category.id);
											else next.delete(category.id);
											return next;
										});
									}}
									className="overflow-hidden rounded-[10px] border border-input"
								>
									<div className="flex items-center gap-2 bg-hover/45 px-3 py-2.5 dark:bg-white/[0.025]">
										<CollapsibleTrigger className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-left">
											<ChevronDown
												className={`size-3.5 shrink-0 text-meta transition-transform ${open ? "" : "-rotate-90"}`}
											/>
											<FolderOpen className="size-3.5 shrink-0 text-petrol dark:text-panel-terminal" />
											<span className="truncate text-[13px] font-semibold text-foreground">
												{category.name}
											</span>
											<span className="rounded-full border border-border bg-card px-2 py-0.5 font-mono text-[9.5px] text-meta">
												{category.memoryCount}
											</span>
										</CollapsibleTrigger>
										<div className="flex shrink-0 items-center">
											<button
												type="button"
												title="Move up"
												disabled={
													reorderSaving || index === 0 || Boolean(query)
												}
												onClick={() => {
													void moveCategory(category.id, -1);
												}}
												className={iconButtonClass}
											>
												<ArrowUp className="size-3.5" />
											</button>
											<button
												type="button"
												title="Move down"
												disabled={
													reorderSaving ||
													index === filteredCategories.length - 1 ||
													Boolean(query)
												}
												onClick={() => {
													void moveCategory(category.id, 1);
												}}
												className={iconButtonClass}
											>
												<ArrowDown className="size-3.5" />
											</button>
											<button
												type="button"
												title="Rename"
												onClick={() => {
													setCategoryDraft({
														id: category.id,
														name: category.name,
													});
												}}
												className={iconButtonClass}
											>
												<Pencil className="size-3.5" />
											</button>
											<button
												type="button"
												title="Delete"
												onClick={() => {
													void deleteCategory(category);
												}}
												className={`${iconButtonClass} hover:text-destructive`}
											>
												<Trash2 className="size-3.5" />
											</button>
										</div>
									</div>
									<CollapsibleContent>
										{category.memories.length === 0 ? (
											<button
												type="button"
												onClick={() => {
													setMemoryDraft({
														id: null,
														categoryId: category.id,
														title: "",
														content: "",
													});
												}}
												className="flex w-full cursor-pointer items-center justify-center gap-1.5 px-4 py-7 text-[12px] font-medium text-meta transition-colors hover:bg-hover/40 hover:text-foreground"
											>
												<Plus className="size-3.5" />
												Add the first memory
											</button>
										) : (
											<div className="divide-y divide-border">
												{category.memories.map((memory) => (
													<div
														key={memory.id}
														className="group flex items-start gap-3 px-4 py-3.5"
													>
														<div className="min-w-0 flex-1">
															<div className="flex flex-wrap items-center gap-2">
																<p className="text-[12.5px] font-semibold text-foreground">
																	{memory.title}
																</p>
																<span
																	className={`rounded-full px-2 py-0.5 text-[9.5px] font-semibold ${
																		memory.source === "assistant"
																			? "bg-petrol/10 text-petrol dark:text-panel-terminal"
																			: "bg-hover text-meta dark:bg-white/5"
																	}`}
																>
																	{memory.source === "assistant"
																		? "Conversation"
																		: "Manual"}
																</span>
															</div>
															<p className="mt-1 whitespace-pre-wrap text-[12.5px] leading-5 text-subtle dark:text-panel-body">
																{memory.content}
															</p>
															<div className="mt-2 flex items-center gap-1.5 font-mono text-[9.5px] text-meta">
																<Clock3 className="size-3" />
																Updated {updatedLabel(memory.updatedAt)}
															</div>
														</div>
														<div className="flex shrink-0 items-center opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
															<button
																type="button"
																title="Edit"
																onClick={() => {
																	setMemoryDraft({
																		id: memory.id,
																		categoryId: memory.categoryId,
																		title: memory.title,
																		content: memory.content,
																	});
																}}
																className={iconButtonClass}
															>
																<Pencil className="size-3.5" />
															</button>
															<button
																type="button"
																title="Delete"
																onClick={() => {
																	void deleteMemory(memory);
																}}
																className={`${iconButtonClass} hover:text-destructive`}
															>
																<Trash2 className="size-3.5" />
															</button>
														</div>
													</div>
												))}
											</div>
										)}
									</CollapsibleContent>
								</Collapsible>
							);
						})
					)}
				</div>
			</section>

			<Dialog
				open={categoryDraft !== null}
				onOpenChange={(open) => {
					if (!open && !saving) setCategoryDraft(null);
				}}
			>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>
							{categoryDraft?.id
								? "Rename category"
								: "New category"}
						</DialogTitle>
						<DialogDescription>
							Group information by topic: home, work, preferences, people…
						</DialogDescription>
					</DialogHeader>
					<input
						autoFocus
						value={categoryDraft?.name ?? ""}
						aria-label="Category name"
						disabled={saving}
						maxLength={100}
						placeholder="Home"
						onChange={(event) => {
							setCategoryDraft((current) =>
								current ? { ...current, name: event.target.value } : current,
							);
						}}
						onKeyDown={(event) => {
							if (event.key === "Enter") {
								event.preventDefault();
								void saveCategory();
							}
						}}
						className={inputClass}
					/>
					<DialogFooter>
						<DialogButton
							variant="outline"
							disabled={saving}
							onClick={() => {
								setCategoryDraft(null);
							}}
						>
							Cancel
						</DialogButton>
						<DialogButton
							disabled={saving || !categoryDraft?.name.trim()}
							onClick={() => {
								void saveCategory();
							}}
						>
							{saving ? "Saving…" : "Save"}
						</DialogButton>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			<MemoryEditor
				draft={memoryDraft}
				categories={library.categories}
				busy={saving}
				onOpenChange={(open) => {
					if (!open) setMemoryDraft(null);
				}}
				onChange={setMemoryDraft}
				onSave={() => {
					void saveMemory();
				}}
			/>
		</div>
	);
}
