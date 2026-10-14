"use client";

import Image from "next/image";
import { useState } from "react";
import { sandboxImageUrl } from "@/lib/api/resources/sandboxes";
import {
	SANDBOX_PROVIDER_ICONS,
	SANDBOX_PROVIDER_LABELS,
} from "@/lib/sandbox-providers";
import { cn } from "@/lib/utils";
import type { SandboxProviderType } from "@/types/sandboxes";

interface SandboxIconProps {
	sandboxId: string;
	imageRevision?: string | null;
	provider: SandboxProviderType;
	size: number;
	className?: string;
}

export function SandboxIcon({
	sandboxId,
	imageRevision,
	provider,
	size,
	className,
}: SandboxIconProps) {
	const [failedUrl, setFailedUrl] = useState<string | null>(null);
	const uploadedUrl = imageRevision
		? sandboxImageUrl(sandboxId, imageRevision)
		: null;
	const customUrl = uploadedUrl !== failedUrl ? uploadedUrl : null;

	return (
		<Image
			unoptimized
			width={size}
			height={size}
			src={customUrl ?? SANDBOX_PROVIDER_ICONS[provider]}
			alt={SANDBOX_PROVIDER_LABELS[provider]}
			className={cn("shrink-0 rounded-[2px] object-contain", className)}
			onError={customUrl ? () => setFailedUrl(customUrl) : undefined}
		/>
	);
}
