import { cookies } from "next/headers";

import { getDatabaseConnection } from "@/lib/api/resources/database-connections";

import { DatabaseConnectionForm } from "../../components/database-connection-form";

interface DatabaseConnectionPageProps {
	params: Promise<{ id: string }>;
}

export default async function DatabaseConnectionPage({
	params,
}: DatabaseConnectionPageProps) {
	const [{ id }, cookieStore] = await Promise.all([params, cookies()]);
	const connection = await getDatabaseConnection(id, {
		cookie: cookieStore.toString(),
	});

	return <DatabaseConnectionForm connection={connection} />;
}
