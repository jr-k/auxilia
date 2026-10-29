"use client";

import { SupervisionBanner } from "@/components/layout/supervision-banner";

export function SupervisionPageFrame({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<div className="flex h-svh min-w-0 flex-col overflow-hidden bg-background">
			<SupervisionBanner loadSession />
			<div className="min-h-0 flex-1 [&>*]:!h-full">{children}</div>
		</div>
	);
}
