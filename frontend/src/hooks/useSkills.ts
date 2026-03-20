/**
 * useSkills — custom hook for skills data fetching.
 *
 * Extracts loadPopularSkills / loadMySubmissions out of SkillsPage so the
 * component only handles rendering while data concerns live here.
 * Non-breaking: SkillsPage can adopt this incrementally by replacing its
 * inline state + effects with a single hook call.
 *
 * Usage
 * ─────
 *   const { popularSkills, mySubmissions, loadingPopular, refresh } =
 *     useSkills(user?.id);
 */

import { useState, useEffect, useCallback } from 'react';
import { skillsApi, Skill, SkillSearchResult } from '@/services/skills';

interface UseSkillsResult {
  /** Verified skills ordered by usage_count, used by the popular grid. */
  popularSkills: Skill[];
  /** Skills whose creator_id matches the current user's id. */
  mySubmissions: Skill[];
  /** True while the popular-skills request is in-flight. */
  loadingPopular: boolean;
  /** True while the my-submissions request is in-flight. */
  loadingSubmissions: boolean;
  /** Re-fetch both lists (call after create / update / delete). */
  refresh: () => void;
  /** Re-fetch only the popular skills list. */
  refreshPopular: () => void;
  /** Re-fetch only the submissions list. */
  refreshSubmissions: () => void;
}

export function useSkills(userId?: string): UseSkillsResult {
  const [popularSkills, setPopularSkills] = useState<Skill[]>([]);
  const [mySubmissions, setMySubmissions] = useState<Skill[]>([]);
  const [loadingPopular, setLoadingPopular] = useState(false);
  const [loadingSubmissions, setLoadingSubmissions] = useState(false);

  const refreshPopular = useCallback(async () => {
    setLoadingPopular(true);
    try {
      const skills = await skillsApi.getPopular(undefined, 9);
      setPopularSkills(skills);
    } catch (error) {
      console.error('[useSkills] Failed to load popular skills:', error);
    } finally {
      setLoadingPopular(false);
    }
  }, []);

  const refreshSubmissions = useCallback(async () => {
    if (!userId) {
      setMySubmissions([]);
      return;
    }
    setLoadingSubmissions(true);
    try {
      const results: SkillSearchResult[] = await skillsApi.search('', {
        creator_id: String(userId),
      });
      setMySubmissions(results.map((r) => r.metadata));
    } catch (error) {
      console.error('[useSkills] Failed to load submissions:', error);
      setMySubmissions([]);
    } finally {
      setLoadingSubmissions(false);
    }
  }, [userId]);

  const refresh = useCallback(() => {
    refreshPopular();
    refreshSubmissions();
  }, [refreshPopular, refreshSubmissions]);

  // Initial load
  useEffect(() => {
    refreshPopular();
  }, [refreshPopular]);

  useEffect(() => {
    refreshSubmissions();
  }, [refreshSubmissions]);

  return {
    popularSkills,
    mySubmissions,
    loadingPopular,
    loadingSubmissions,
    refresh,
    refreshPopular,
    refreshSubmissions,
  };
}