import { api } from "@/lib/api/client";
import type {
	Memory,
	MemoryCategory,
	MemoryLibrary,
	MemoryPreferences,
} from "@/types/memories";

export async function getMemoryLibrary(query?: string): Promise<MemoryLibrary> {
	const response = await api.get<MemoryLibrary>("/memories/", {
		params: query?.trim() ? { q: query.trim() } : undefined,
	});
	return response.data;
}

export async function createMemoryCategory(
	name: string,
): Promise<MemoryCategory> {
	const response = await api.post<MemoryCategory>("/memories/categories", {
		name,
	});
	return response.data;
}

export async function updateMemoryCategory(
	categoryId: string,
	name: string,
): Promise<MemoryCategory> {
	const response = await api.patch<MemoryCategory>(
		`/memories/categories/${categoryId}`,
		{ name },
	);
	return response.data;
}

export async function reorderMemoryCategories(
	categoryIds: string[],
): Promise<MemoryCategory[]> {
	const response = await api.put<MemoryCategory[]>(
		"/memories/categories/order",
		{ categoryIds },
	);
	return response.data;
}

export async function deleteMemoryCategory(categoryId: string): Promise<void> {
	await api.delete(`/memories/categories/${categoryId}`);
}

export async function createMemory(data: {
	categoryId: string;
	title: string;
	content: string;
}): Promise<Memory> {
	const response = await api.post<Memory>("/memories/", data);
	return response.data;
}

export async function updateMemory(
	memoryId: string,
	data: {
		categoryId?: string;
		title?: string;
		content?: string;
	},
): Promise<Memory> {
	const response = await api.patch<Memory>(`/memories/${memoryId}`, data);
	return response.data;
}

export async function deleteMemory(memoryId: string): Promise<void> {
	await api.delete(`/memories/${memoryId}`);
}

export async function getMemoryPreferences(): Promise<MemoryPreferences> {
	const response = await api.get<MemoryPreferences>("/memories/preferences");
	return response.data;
}

export async function updateMemoryPreferences(
	autoCaptureEnabled: boolean,
): Promise<MemoryPreferences> {
	const response = await api.patch<MemoryPreferences>("/memories/preferences", {
		autoCaptureEnabled,
	});
	return response.data;
}
