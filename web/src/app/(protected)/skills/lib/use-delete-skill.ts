"use client";

import { useState } from "react";
import * as skillsApi from "@/lib/api/resources/skills";
import { useAgentsStore } from "@/stores/agents-store";
import { useSkillsStore } from "@/stores/skills-store";
import type { BoundAgent } from "@/types/agents";
import type { Skill, SkillSummary } from "@/types/skills";

interface DeleteGuard {
	skill: SkillSummary;
	agents: BoundAgent[];
}

interface UseDeleteSkillOptions {
	onDeleted?: (skill: SkillSummary) => void;
	onError?: (error: unknown) => void;
}

/**
 * The two-step delete every skills screen shares: a skill in use opens the
 * detach-and-delete acknowledgement; a free one asks for the standard
 * confirmation. The binding lookup is live so a stale library count cannot
 * silently skip the stronger confirmation.
 */
export function useDeleteSkill({ onDeleted, onError }: UseDeleteSkillOptions = {}) {
	const deleteSkill = useSkillsStore((state) => state.deleteSkill);
	const removeSkillBinding = useAgentsStore((state) => state.removeSkillBinding);
	const [guard, setGuard] = useState<DeleteGuard | null>(null);
	const [pending, setPending] = useState<SkillSummary | null>(null);

	const requestDelete = async (skill: SkillSummary | Skill) => {
		try {
			const agents = await skillsApi.listSkillAgents(skill.id);
			if (agents.length > 0) {
				setGuard({ skill, agents });
				return;
			}
			setPending(skill);
		} catch (error) {
			onError?.(error);
		}
	};

	const confirmDelete = async () => {
		if (!pending) return;
		try {
			await deleteSkill(pending.id);
			removeSkillBinding(pending.id);
			onDeleted?.(pending);
			setPending(null);
		} catch (error) {
			onError?.(error);
			throw error;
		}
	};

	const confirmDetachAndDelete = async () => {
		if (!guard) return;
		try {
			await deleteSkill(guard.skill.id, { detachAgents: true });
			removeSkillBinding(guard.skill.id);
			onDeleted?.(guard.skill);
			setGuard(null);
		} catch (error) {
			onError?.(error);
			throw error;
		}
	};

	return {
		guard,
		pending,
		requestDelete,
		confirmDelete,
		confirmDetachAndDelete,
		clearGuard: () => {
			setGuard(null);
		},
		clearPending: () => {
			setPending(null);
		},
	};
}
