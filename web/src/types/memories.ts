export type MemorySource = "manual" | "assistant";

export interface Memory {
	id: string;
	categoryId: string;
	categoryName: string;
	key: string;
	title: string;
	content: string;
	source: MemorySource;
	sourceThreadId: string | null;
	createdAt: string;
	updatedAt: string;
}

export interface MemoryCategory {
	id: string;
	name: string;
	position: number;
	memoryCount: number;
	createdAt: string;
	updatedAt: string;
}

export interface MemoryCategoryGroup extends MemoryCategory {
	memories: Memory[];
}

export interface MemoryLibrary {
	categories: MemoryCategoryGroup[];
	total: number;
}

export interface MemoryPreferences {
	autoCaptureEnabled: boolean;
}
