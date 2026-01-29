import { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Bot, Clock } from 'lucide-react';
import type { TranscriptEntry } from '../types';

interface TranscriptProps {
  entries: TranscriptEntry[];
  currentState: string;
}

const STATE_LABELS: Record<string, { label: string; color: string }> = {
  greeting: { label: 'Greeting', color: 'text-blue-400' },
  identify_intent: { label: 'Understanding Intent', color: 'text-purple-400' },
  collecting_reservation: { label: 'Collecting Details', color: 'text-accent-copper' },
  checking_availability: { label: 'Checking Availability', color: 'text-yellow-400' },
  offering_alternatives: { label: 'Offering Alternatives', color: 'text-orange-400' },
  confirming: { label: 'Confirming', color: 'text-green-400' },
  complete: { label: 'Complete', color: 'text-accent-gold' },
  faq_mode: { label: 'Answering Questions', color: 'text-cyan-400' },
  modify_flow: { label: 'Modifying Reservation', color: 'text-indigo-400' },
  cancel_flow: { label: 'Cancellation', color: 'text-red-400' },
  waitlist_flow: { label: 'Waitlist', color: 'text-pink-400' },
};

export function Transcript({ entries, currentState }: TranscriptProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const stateInfo = STATE_LABELS[currentState] || { label: currentState, color: 'text-gray-400' };

  return (
    <div className="glass rounded-2xl p-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display text-xl text-accent-gold">Live Transcript</h2>
        <div className="flex items-center gap-2 px-3 py-1 bg-deep-purple rounded-full">
          <div className={`w-2 h-2 rounded-full ${stateInfo.color.replace('text-', 'bg-')}`} />
          <span className={`text-sm ${stateInfo.color}`}>{stateInfo.label}</span>
        </div>
      </div>

      {/* Transcript List */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-3 min-h-0 pr-2"
      >
        <AnimatePresence initial={false}>
          {entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <Bot className="w-12 h-12 mb-3 opacity-50" />
              <p>Start a call to see the transcript</p>
            </div>
          ) : (
            entries.map((entry, index) => (
              <motion.div
                key={`${entry.timestamp}-${index}`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className={`p-4 rounded-xl ${
                  entry.speaker === 'user' ? 'transcript-user' : 'transcript-agent'
                }`}
              >
                <div className="flex items-start gap-3">
                  {/* Avatar */}
                  <div className={`p-2 rounded-lg ${
                    entry.speaker === 'user' ? 'bg-accent-copper/20' : 'bg-accent-gold/20'
                  }`}>
                    {entry.speaker === 'user' ? (
                      <User className={`w-4 h-4 ${
                        entry.speaker === 'user' ? 'text-accent-copper' : 'text-accent-gold'
                      }`} />
                    ) : (
                      <Bot className="w-4 h-4 text-accent-gold" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`font-medium ${
                        entry.speaker === 'user' ? 'text-accent-copper' : 'text-accent-gold'
                      }`}>
                        {entry.speaker === 'user' ? 'Caller' : 'Receptionist'}
                      </span>
                      <span className="text-xs text-gray-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatTime(entry.timestamp)}
                      </span>
                    </div>
                    <p className="text-soft-cream leading-relaxed">{entry.text}</p>
                  </div>
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
