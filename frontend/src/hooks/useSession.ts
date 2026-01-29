import { useState, useCallback } from 'react';
import type { Session, PersonaType } from '../types';

const API_BASE = '/api';

interface UseSessionReturn {
  session: Session | null;
  isLoading: boolean;
  error: string | null;
  createSession: () => Promise<void>;
  updatePersona: (personaType: PersonaType) => Promise<void>;
  updateVoice: (voiceId: string) => Promise<void>;
  injectFact: (fact: string) => Promise<void>;
  refreshSession: () => Promise<void>;
}

export function useSession(): UseSessionReturn {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createSession = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ restaurant_id: 1 }),
      });

      if (!response.ok) throw new Error('Failed to create session');

      const data = await response.json();

      // Fetch full session details
      const sessionResponse = await fetch(`${API_BASE}/sessions/${data.session_id}`);
      if (!sessionResponse.ok) throw new Error('Failed to get session');

      const sessionData = await sessionResponse.json();
      setSession(sessionData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshSession = useCallback(async () => {
    if (!session?.session_id) return;

    try {
      const response = await fetch(`${API_BASE}/sessions/${session.session_id}`);
      if (!response.ok) throw new Error('Failed to refresh session');

      const data = await response.json();
      setSession(data);
    } catch (err) {
      console.error('Failed to refresh session:', err);
    }
  }, [session?.session_id]);

  const updatePersona = useCallback(async (personaType: PersonaType) => {
    if (!session?.session_id) return;

    try {
      const response = await fetch(`${API_BASE}/sessions/${session.session_id}/persona`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ persona_type: personaType }),
      });

      if (!response.ok) throw new Error('Failed to update persona');

      const data = await response.json();
      setSession(prev => prev ? {
        ...prev,
        persona_type: personaType,
        voice_id: data.voice_id,
      } : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [session?.session_id]);

  const updateVoice = useCallback(async (voiceId: string) => {
    if (!session?.session_id) return;

    try {
      const response = await fetch(`${API_BASE}/sessions/${session.session_id}/voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice_id: voiceId }),
      });

      if (!response.ok) throw new Error('Failed to update voice');

      setSession(prev => prev ? { ...prev, voice_id: voiceId } : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [session?.session_id]);

  const injectFact = useCallback(async (fact: string) => {
    if (!session?.session_id) return;

    try {
      const response = await fetch(
        `${API_BASE}/sessions/${session.session_id}/inject-fact?fact=${encodeURIComponent(fact)}`,
        { method: 'POST' }
      );

      if (!response.ok) throw new Error('Failed to inject fact');

      const data = await response.json();
      setSession(prev => prev ? { ...prev, facts: data.facts } : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [session?.session_id]);

  return {
    session,
    isLoading,
    error,
    createSession,
    updatePersona,
    updateVoice,
    injectFact,
    refreshSession,
  };
}
