import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import * as agentsApi from "@/lib/api/resources/agents";

export default async function HomePage() {
	const cookieStore = await cookies();
	const agents = await agentsApi.listAgents({
		cookie: cookieStore.toString(),
	});
	const defaultAgent = agents.find((agent) => agent.isDefault);

	redirect(defaultAgent ? `/agents/${defaultAgent.id}/chat` : "/agents");
}
