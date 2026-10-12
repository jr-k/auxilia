"use client";

import { Bell, Check, Plus, Send, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { useConfirmDialog } from "@/components/providers/dialog-provider";
import { SlackLogo } from "@/components/slack-logo";
import { Switch } from "@/components/ui/switch";
import { getApiErrorMessage } from "@/lib/api/errors";
import * as notificationsApi from "@/lib/api/resources/notifications";
import type {
	NotificationChannel,
	NotificationChannelType,
} from "@/types/notifications";

const inputClass =
	"w-full rounded-[8px] border border-input bg-card px-3 py-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-meta focus:border-petrol";

export default function ProfileNotifications() {
	const confirmDialog = useConfirmDialog();
	const [channels, setChannels] = useState<NotificationChannel[]>([]);
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [updatingIds, setUpdatingIds] = useState<Set<string>>(new Set());
	const updatingIdsRef = useRef(new Set<string>());
	const [adding, setAdding] = useState(false);
	const [saving, setSaving] = useState(false);
	const [name, setName] = useState("");
	const [type, setType] = useState<NotificationChannelType>("browser");
	const [slackChannelId, setSlackChannelId] = useState("");
	const hasBrowserChannel = channels.some(
		(channel) => channel.channelType === "browser",
	);

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError(null);
		try {
			setChannels(await notificationsApi.listChannels());
		} catch (error: unknown) {
			const message = getApiErrorMessage(
				error,
				"Could not load notification channels.",
			);
			setLoadError(message);
			toast.error(message);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		const timeoutId = window.setTimeout(() => {
			void load();
		}, 0);
		return () => {
			window.clearTimeout(timeoutId);
		};
	}, [load]);

	const resetForm = () => {
		setAdding(false);
		setName("");
		setType("browser");
		setSlackChannelId("");
	};

	const create = async () => {
		const cleanName = name.trim();
		if (!cleanName) return;
		if (type === "slack" && !slackChannelId.trim()) return;
		if (
			type === "browser" &&
			"Notification" in window &&
			Notification.permission === "default"
		) {
			await Notification.requestPermission();
		}
		setSaving(true);
		try {
			const channel = await notificationsApi.createChannel({
				name: cleanName,
				channelType: type,
				enabled: true,
				isDefault: channels.length === 0,
				config:
					type === "slack"
						? { channelId: slackChannelId.trim() }
						: undefined,
			});
			setChannels((current) => [...current, channel]);
			resetForm();
		} catch (error: unknown) {
			toast.error(getApiErrorMessage(error, "Could not create the channel."));
		} finally {
			setSaving(false);
		}
	};

	const patch = async (
		channel: NotificationChannel,
		update: { enabled?: boolean; isDefault?: boolean },
	) => {
		if (updatingIdsRef.current.has(channel.id)) return;
		updatingIdsRef.current.add(channel.id);
		setUpdatingIds(new Set(updatingIdsRef.current));
		setChannels((current) =>
			current.map((item) =>
				item.id === channel.id ? { ...item, ...update } : item,
			),
		);
		try {
			const updated = await notificationsApi.updateChannel(channel.id, update);
			setChannels((current) =>
				current.map((item) => (item.id === updated.id ? updated : item)),
			);
		} catch (error: unknown) {
			setChannels((current) =>
				current.map((item) => (item.id === channel.id ? channel : item)),
			);
			toast.error(getApiErrorMessage(error, "Could not update the channel."));
		} finally {
			updatingIdsRef.current.delete(channel.id);
			setUpdatingIds(new Set(updatingIdsRef.current));
		}
	};

	const remove = async (channel: NotificationChannel) => {
		const confirmed = await confirmDialog({
			title: `Delete “${channel.name}”?`,
			description:
				"Scheduled notifications explicitly using this channel will no longer be delivered to it.",
			confirmLabel: "Delete channel",
			destructive: true,
		});
		if (!confirmed) return;
		try {
			await notificationsApi.deleteChannel(channel.id);
			setChannels((current) =>
				current.filter((item) => item.id !== channel.id),
			);
		} catch (error: unknown) {
			toast.error(getApiErrorMessage(error, "Could not delete the channel."));
		}
	};

	const test = async (channel: NotificationChannel) => {
		if (
			channel.channelType === "browser" &&
			"Notification" in window &&
			Notification.permission === "default"
		) {
			await Notification.requestPermission();
		}
		try {
			const result = await notificationsApi.testChannel(channel.id);
			if (result.failed[channel.name]) {
				toast.error(result.failed[channel.name]);
				return;
			}
			toast.success(`Test sent to ${channel.name}.`);
		} catch (error: unknown) {
			toast.error(getApiErrorMessage(error, "Could not test the channel."));
		}
	};

	return (
		<div>
			<div className="mb-1.5 flex items-center gap-2.5">
				<span className="text-[10.5px] font-semibold text-subtle dark:text-panel-dim">
					Notification channels
				</span>
				<span className="flex-1" />
				{!adding && !loading && loadError === null && (
					<button
						type="button"
						onClick={() => {
							setType(hasBrowserChannel ? "slack" : "browser");
							setAdding(true);
						}}
						className="flex cursor-pointer items-center gap-1.5 rounded-[7px] bg-primary px-3.5 py-2 text-[12px] font-semibold text-primary-foreground transition-opacity hover:opacity-90"
					>
						<Plus className="size-3.5" />
						Add channel
					</button>
				)}
			</div>
			<p className="mb-3.5 max-w-[620px] text-[13px] leading-[1.55] text-subtle dark:text-panel-body">
				Agents use your default channels whenever you ask to be notified.
			</p>

			{adding && (
				<div className="mb-3 rounded-[10px] border border-petrol/30 bg-petrol/[0.035] p-4 dark:bg-petrol/10">
					<div className="grid gap-3 sm:grid-cols-2">
						<label>
							<span className="mb-1.5 block text-[10px] font-semibold text-subtle">
								Name
							</span>
							<input
								value={name}
								onChange={(event) => {
									setName(event.target.value);
								}}
								placeholder={type === "browser" ? "Auxilia" : "Support"}
								className={inputClass}
							/>
						</label>
						<label>
							<span className="mb-1.5 block text-[10px] font-semibold text-subtle">
								Technology
							</span>
							<select
								value={type}
								onChange={(event) => {
									setType(event.target.value as NotificationChannelType);
								}}
								className={inputClass}
							>
								<option value="browser" disabled={hasBrowserChannel}>
									Browser
								</option>
								<option value="slack">Slack</option>
							</select>
						</label>
					</div>
					{type === "slack" && (
						<label className="mt-3 block">
							<span className="mb-1.5 block text-[10px] font-semibold text-subtle">
								Slack channel ID
							</span>
							<input
								value={slackChannelId}
								onChange={(event) => {
									setSlackChannelId(event.target.value);
								}}
								placeholder="C0123456789"
								className={inputClass}
							/>
							<span className="mt-1.5 block text-[11px] text-meta">
								Copy it from Slack&apos;s channel details. An active workspace
								or agent bot must already be in the channel.
							</span>
						</label>
					)}
					<div className="mt-4 flex justify-end gap-2">
						<button
							type="button"
							onClick={resetForm}
							className="flex cursor-pointer items-center gap-1.5 rounded-[7px] border border-input px-3 py-2 text-[12px] font-semibold text-subtle"
						>
							<X className="size-3.5" />
							Cancel
						</button>
						<button
							type="button"
							disabled={
								saving ||
								!name.trim() ||
								(type === "slack" && !slackChannelId.trim())
							}
							onClick={() => {
								void create();
							}}
							className="flex cursor-pointer items-center gap-1.5 rounded-[7px] bg-petrol px-3 py-2 text-[12px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
						>
							<Check className="size-3.5" />
							Create
						</button>
					</div>
				</div>
			)}

			<div className="overflow-hidden rounded-[10px] border border-border bg-card dark:border-white/10">
				{loading ? (
					<div className="h-24 animate-pulse bg-muted/40" />
				) : loadError ? (
					<div className="px-5 py-8 text-center">
						<p className="text-[13px] font-medium text-subtle">
							{loadError}
						</p>
						<button
							type="button"
							onClick={() => {
								void load();
							}}
							className="mt-3 cursor-pointer rounded-[7px] border border-input px-3 py-2 text-[12px] font-semibold text-foreground transition-colors hover:bg-muted"
						>
							Retry
						</button>
					</div>
				) : channels.length === 0 ? (
					<div className="px-5 py-9 text-center">
						<Bell className="mx-auto mb-2 size-5 text-meta" />
						<p className="text-[13px] font-medium text-subtle">
							No notification channel configured.
						</p>
					</div>
				) : (
					channels.map((channel, index) => (
						<div
							key={channel.id}
							className={`flex flex-wrap items-center gap-3 px-4 py-3.5 sm:flex-nowrap ${
								index > 0 ? "border-t border-hairline" : ""
							}`}
						>
							{channel.channelType === "slack" ? (
								<SlackLogo className="size-9 rounded-[9px]" />
							) : (
								<span className="flex size-9 shrink-0 items-center justify-center rounded-[9px] border border-border bg-background text-petrol">
									<Bell className="size-4" />
								</span>
							)}
							<div className="min-w-0 flex-1">
								<p className="truncate text-[13px] font-semibold text-foreground">
									{channel.name}
								</p>
								<p className="mt-0.5 truncate font-mono text-[10.5px] text-meta">
									{channel.channelType === "slack"
										? channel.config.channelId
										: "open Auxilia sessions"}
								</p>
							</div>
							<div className="ml-12 flex w-full items-center justify-end gap-3 sm:ml-0 sm:w-auto">
								<label className="flex items-center gap-2 text-[11px] font-medium text-subtle">
									Default
									<Switch
										checked={channel.isDefault}
										disabled={
											!channel.enabled || updatingIds.has(channel.id)
										}
										onCheckedChange={(checked) => {
											void patch(channel, { isDefault: checked });
										}}
									/>
								</label>
								<label className="flex items-center gap-2 text-[11px] font-medium text-subtle">
									Active
									<Switch
										aria-label={`Enable ${channel.name}`}
										checked={channel.enabled}
										disabled={updatingIds.has(channel.id)}
										onCheckedChange={(checked) => {
											void patch(channel, { enabled: checked });
										}}
									/>
								</label>
								{channel.channelType === "browser" && (
									<button
										type="button"
										title="Send test"
										aria-label={`Send a test to ${channel.name}`}
										disabled={
											!channel.enabled || updatingIds.has(channel.id)
										}
										onClick={() => {
											void test(channel);
										}}
										className="flex size-8 cursor-pointer items-center justify-center rounded-[7px] text-meta transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-meta"
									>
										<Send className="size-3.5" />
									</button>
								)}
								<button
									type="button"
									title="Delete channel"
									aria-label={`Delete ${channel.name}`}
									disabled={updatingIds.has(channel.id)}
									onClick={() => {
										void remove(channel);
									}}
									className="flex size-8 cursor-pointer items-center justify-center rounded-[7px] text-meta transition-colors hover:bg-destructive/10 hover:text-destructive disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-meta"
								>
									<Trash2 className="size-3.5" />
								</button>
							</div>
						</div>
					))
				)}
			</div>
		</div>
	);
}
