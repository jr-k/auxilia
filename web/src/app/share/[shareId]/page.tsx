import type { Metadata } from "next";
import { PublicConversationView } from "./public-conversation-view";

export const metadata: Metadata = {
	title: "Shared conversation",
	referrer: "no-referrer",
	robots: {
		index: false,
		follow: false,
		nocache: true,
	},
};

export default async function SharedConversationPage({
	params,
}: {
	params: Promise<{ shareId: string }>;
}) {
	const { shareId } = await params;
	return <PublicConversationView shareId={shareId} />;
}
