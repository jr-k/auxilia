"use client";

import { useCallback, useEffect, useState } from "react";
import { TelegramLogo } from "@/components/telegram-logo";
import { Switch } from "@/components/ui/switch";
import { getApiErrorMessage, isApiError } from "@/lib/api/errors";
import * as notificationsApi from "@/lib/api/resources/notifications";

export default function WorkspaceTelegram({
	onForbidden,
}: {
	onForbidden: () => void;
}) {
	const [enabled, setEnabled] = useState(false);
	const [loaded, setLoaded] = useState(false);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const load = useCallback(async () => {
		try {
			const settings = await notificationsApi.getTelegramSettings();
			setEnabled(settings.enabled);
			setLoaded(true);
		} catch (loadError: unknown) {
			if (isApiError(loadError) && loadError.status === 403) {
				onForbidden();
				return;
			}
			setError(getApiErrorMessage(loadError, "Could not load Telegram settings."));
		}
	}, [onForbidden]);

	useEffect(() => {
		const timeout = window.setTimeout(() => {
			void load();
		}, 0);
		return () => {
			window.clearTimeout(timeout);
		};
	}, [load]);

	const toggle = async (checked: boolean) => {
		setEnabled(checked);
		setSaving(true);
		setError(null);
		try {
			const updated = await notificationsApi.updateTelegramSettings(checked);
			setEnabled(updated.enabled);
		} catch (updateError: unknown) {
			setEnabled(!checked);
			setError(
				getApiErrorMessage(updateError, "Could not update Telegram settings."),
			);
		} finally {
			setSaving(false);
		}
	};

	if (!loaded) {
		return (
			<div className="h-20 animate-pulse border-t border-hairline bg-card" />
		);
	}

	return (
		<>
			<div className="flex items-center gap-3 border-t border-hairline px-4 py-4">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-[8px] border border-border bg-background shadow-sm dark:border-white/10">
					<TelegramLogo className="size-[62%]" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-[13px] font-semibold text-foreground">
						Telegram integration
					</p>
					<p className="mt-0.5 text-[11.5px] text-meta">
						{enabled
							? "Enabled for agent-specific bots"
							: "Disabled for all agent bots"}
					</p>
				</div>
				<Switch
					aria-label="Enable Telegram side channels"
					checked={enabled}
					disabled={saving}
					onCheckedChange={(checked) => {
						void toggle(checked);
					}}
					className="cursor-pointer data-[state=checked]:bg-petrol"
				/>
			</div>
			{error && (
				<div className="border-t border-hairline px-4 py-3 text-[12px] text-destructive">
					{error}
				</div>
			)}
		</>
	);
}
