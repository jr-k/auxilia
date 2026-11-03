import NotificationOpen from "./notification-open";

function value(
	input: string | string[] | undefined,
): string | null {
	return typeof input === "string" && input ? input : null;
}

export default async function NotificationOpenPage({
	searchParams,
}: {
	searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
	const params = await searchParams;
	return (
		<NotificationOpen
			workspaceId={value(params.workspaceId)}
			agentId={value(params.agentId)}
			threadId={value(params.threadId)}
		/>
	);
}
