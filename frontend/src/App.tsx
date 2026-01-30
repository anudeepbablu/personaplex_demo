import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Building2, Loader2, Activity } from 'lucide-react';

import { CallPanel } from './components/CallPanel';
import { Transcript } from './components/Transcript';
import { ExtractedFields } from './components/ExtractedFields';
import { PersonaControls } from './components/PersonaControls';
import { ActionButtons } from './components/ActionButtons';
import { AvailabilityPanel } from './components/AvailabilityPanel';

import { useSession } from './hooks/useSession';
import { useAudioStream } from './hooks/useAudioStream';

import type {
  TranscriptEntry,
  ExtractedFields as ExtractedFieldsType,
  SpeakingState,
  TimeSlot,
  PersonaType,
} from './types';

const INITIAL_EXTRACTED: ExtractedFieldsType = {
  guest_name: null,
  phone: null,
  party_size: null,
  date_time: null,
  area_pref: null,
  notes: null,
  intent: null,
  confirmation_code: null,
};

function App() {
  // Session state
  const {
    session,
    isLoading,
    error,
    createSession,
    updatePersona,
    updateVoice,
  } = useSession();

  // Local UI state
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [extracted, setExtracted] = useState<ExtractedFieldsType>(INITIAL_EXTRACTED);
  const [missingFields, setMissingFields] = useState<string[]>(['guest_name', 'phone', 'party_size', 'date_time']);
  const [conversationState, setConversationState] = useState('greeting');
  const [speakingState, setSpeakingState] = useState<SpeakingState>({ user_speaking: false, agent_speaking: false });
  const [availableSlots, setAvailableSlots] = useState<TimeSlot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null);

  // Audio stream handlers - accumulate consecutive words from same speaker
  const handleTranscript = useCallback((entry: TranscriptEntry) => {
    console.log('[App] 💬 Transcript:', entry.speaker, '-', entry.text);
    setTranscript(prev => {
      // If there are previous entries and the last one is from the same speaker,
      // append the text to the last entry instead of creating a new one
      if (prev.length > 0) {
        const lastEntry = prev[prev.length - 1];
        if (lastEntry.speaker === entry.speaker) {
          // Append to existing entry
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...lastEntry,
            text: lastEntry.text + entry.text,
            timestamp: entry.timestamp, // Update timestamp to latest
          };
          return updated;
        }
      }
      // Different speaker or first entry - add new entry
      return [...prev, entry];
    });
  }, []);

  const handleExtraction = useCallback((data: ExtractedFieldsType) => {
    console.log('[App] 📋 Extraction update:', data);
    setExtracted(data);
  }, []);

  const handleStateChange = useCallback((state: string) => {
    console.log('[App] 🔄 State change:', state);
    setConversationState(state);
  }, []);

  const handleSpeakingChange = useCallback((speaking: SpeakingState) => {
    console.log('[App] 🎤 Speaking change - user:', speaking.user_speaking, 'agent:', speaking.agent_speaking);
    setSpeakingState(speaking);
  }, []);

  const handleError = useCallback((err: string) => {
    console.error('[App] 🚨 Audio stream error:', err);
  }, []);

  // Audio stream hook
  const {
    isConnected,
    isRecording,
    startRecording,
    stopRecording,
    sendTextInput,
    sendControl,
    audioLevel,
  } = useAudioStream({
    sessionId: session?.session_id || null,
    onTranscript: handleTranscript,
    onExtraction: handleExtraction,
    onStateChange: handleStateChange,
    onSpeakingChange: handleSpeakingChange,
    onError: handleError,
  });

  // Update missing fields when extracted changes
  useEffect(() => {
    const required = ['guest_name', 'phone', 'party_size', 'date_time'];
    const missing = required.filter(f => !extracted[f as keyof ExtractedFieldsType]);
    setMissingFields(missing);
  }, [extracted]);

  // Initialize session on mount - only once
  useEffect(() => {
    console.log('[App] 🚀 Mount effect - session:', session?.session_id, 'isLoading:', isLoading, 'error:', error);
    if (!session && !isLoading && !error) {
      console.log('[App] 📞 Creating new session...');
      createSession();
    }
  }, []); // Empty deps - only run on mount

  // Action handlers
  const handleConfirm = async () => {
    // In a real implementation, this would call the API
    console.log('Confirming reservation:', extracted);
    setConversationState('complete');
  };

  const handleModify = () => {
    sendControl('inject_fact', { fact: 'Customer wants to modify their reservation' });
  };

  const handleCancel = () => {
    sendControl('inject_fact', { fact: 'Customer wants to cancel their reservation' });
  };

  const handleWaitlist = () => {
    sendControl('inject_fact', { fact: 'Requested time is not available. Offer waitlist.' });
  };

  const handleSendSMS = async () => {
    console.log('Sending SMS to:', extracted.phone);
  };

  const handleSelectSlot = (slot: TimeSlot) => {
    setSelectedSlot(slot);
    setExtracted(prev => ({
      ...prev,
      date_time: slot.time,
      area_pref: slot.area,
    }));
  };

  // Loading state
  if (isLoading && !session) {
    return (
      <div className="min-h-screen bg-midnight flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center gap-4"
        >
          <Loader2 className="w-12 h-12 text-accent-gold animate-spin" />
          <p className="text-gray-400">Initializing Front Desk Console...</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-midnight relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-midnight via-deep-purple to-royal opacity-80" />
      <div className="absolute inset-0 noise-overlay" />

      {/* Decorative elements */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-accent-gold/5 rounded-full blur-3xl" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-accent-copper/5 rounded-full blur-3xl" />

      {/* Main content */}
      <div className="relative z-10 min-h-screen">
        {/* Header */}
        <header className="border-b border-gray-800/50 bg-midnight/50 backdrop-blur-sm">
          <div className="max-w-screen-2xl mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-2 bg-gradient-to-br from-accent-gold to-accent-copper rounded-xl">
                  <Building2 className="w-6 h-6 text-midnight" />
                </div>
                <div>
                  <h1 className="font-display text-2xl text-gradient">Front Desk Console</h1>
                  <p className="text-sm text-gray-500">PersonaPlex Restaurant Receptionist</p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                {session && (
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-500">Session:</span>
                    <code className="font-mono text-accent-gold bg-deep-purple px-3 py-1 rounded">
                      {session.session_id}
                    </code>
                  </div>
                )}
                <a
                  href="#/dashboard"
                  className="flex items-center gap-2 px-3 py-2 rounded-lg bg-deep-purple hover:bg-royal border border-gray-700/50 transition-colors"
                >
                  <Activity className="w-4 h-4 text-green-400" />
                  <span className="text-sm text-gray-300">Dashboard</span>
                </a>
              </div>
            </div>
          </div>
        </header>

        {/* Main Grid */}
        <main className="max-w-screen-2xl mx-auto px-6 py-6">
          <div className="grid grid-cols-12 gap-6 h-[calc(100vh-140px)]">
            {/* Left Column - Call Controls & Persona */}
            <div className="col-span-3 space-y-6 overflow-y-auto">
              <CallPanel
                isConnected={isConnected}
                isRecording={isRecording}
                userSpeaking={speakingState.user_speaking}
                agentSpeaking={speakingState.agent_speaking}
                audioLevel={audioLevel}
                onStartCall={startRecording}
                onEndCall={stopRecording}
                onTextInput={sendTextInput}
              />

              <PersonaControls
                currentPersona={session?.persona_type || 'family'}
                currentVoice={session?.voice_id || 'NATF1'}
                onPersonaChange={updatePersona}
                onVoiceChange={updateVoice}
              />
            </div>

            {/* Center Column - Transcript */}
            <div className="col-span-5 overflow-hidden">
              <Transcript
                entries={transcript}
                currentState={conversationState}
              />
            </div>

            {/* Right Column - Extracted Fields & Actions */}
            <div className="col-span-4 space-y-6 overflow-y-auto">
              <ExtractedFields
                fields={extracted}
                missingFields={missingFields}
              />

              <AvailabilityPanel
                slots={availableSlots}
                selectedSlot={selectedSlot}
                onSelectSlot={handleSelectSlot}
              />

              <ActionButtons
                fields={extracted}
                missingFields={missingFields}
                currentState={conversationState}
                onConfirm={handleConfirm}
                onModify={handleModify}
                onCancel={handleCancel}
                onWaitlist={handleWaitlist}
                onSendSMS={handleSendSMS}
              />
            </div>
          </div>
        </main>
      </div>

      {/* Error Toast */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            className="fixed bottom-6 right-6 bg-red-900/90 border border-red-700 text-red-200 px-6 py-4 rounded-xl shadow-lg"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
