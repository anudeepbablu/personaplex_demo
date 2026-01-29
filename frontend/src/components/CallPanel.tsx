import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Phone, PhoneOff, Volume2 } from 'lucide-react';

interface CallPanelProps {
  isConnected: boolean;
  isRecording: boolean;
  userSpeaking: boolean;
  agentSpeaking: boolean;
  audioLevel: number;
  onStartCall: () => void;
  onEndCall: () => void;
  onTextInput?: (text: string) => void;
}

export function CallPanel({
  isConnected,
  isRecording,
  userSpeaking,
  agentSpeaking,
  audioLevel,
  onStartCall,
  onEndCall,
  onTextInput,
}: CallPanelProps) {
  const [textInput, setTextInput] = useState('');

  const handleSubmitText = (e: React.FormEvent) => {
    e.preventDefault();
    if (textInput.trim() && onTextInput) {
      onTextInput(textInput.trim());
      setTextInput('');
    }
  };

  return (
    <div className="glass rounded-2xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl text-accent-gold">Call Controls</h2>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-500'}`} />
          <span className="text-sm text-gray-400">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Duplex Indicator */}
      <div className="flex items-center justify-center gap-8 py-4">
        {/* User Speaking */}
        <motion.div
          className={`flex flex-col items-center gap-2 p-4 rounded-xl transition-colors ${
            userSpeaking ? 'bg-accent-copper/20' : 'bg-deep-purple'
          }`}
          animate={{ scale: userSpeaking ? 1.05 : 1 }}
        >
          <div className="relative">
            <Mic className={`w-8 h-8 ${userSpeaking ? 'text-accent-copper' : 'text-gray-500'}`} />
            {userSpeaking && (
              <motion.div
                className="absolute -inset-2 rounded-full border-2 border-accent-copper"
                animate={{ scale: [1, 1.3, 1], opacity: [1, 0, 1] }}
                transition={{ duration: 1, repeat: Infinity }}
              />
            )}
          </div>
          <span className="text-sm text-gray-400">You</span>
          {userSpeaking && <span className="text-xs text-accent-copper">Speaking...</span>}
        </motion.div>

        {/* Waveform */}
        <div className="flex items-end gap-1 h-16">
          {[0, 1, 2, 3, 4].map((i) => (
            <motion.div
              key={i}
              className={`w-1.5 rounded-full ${
                agentSpeaking ? 'bg-accent-gold' : userSpeaking ? 'bg-accent-copper' : 'bg-gray-600'
              }`}
              animate={{
                height: isRecording || agentSpeaking
                  ? [8, 8 + Math.random() * 40 * audioLevel, 8]
                  : 8,
              }}
              transition={{
                duration: 0.15,
                delay: i * 0.05,
                repeat: Infinity,
              }}
            />
          ))}
        </div>

        {/* Agent Speaking */}
        <motion.div
          className={`flex flex-col items-center gap-2 p-4 rounded-xl transition-colors ${
            agentSpeaking ? 'bg-accent-gold/20' : 'bg-deep-purple'
          }`}
          animate={{ scale: agentSpeaking ? 1.05 : 1 }}
        >
          <div className="relative">
            <Volume2 className={`w-8 h-8 ${agentSpeaking ? 'text-accent-gold' : 'text-gray-500'}`} />
            {agentSpeaking && (
              <motion.div
                className="absolute -inset-2 rounded-full border-2 border-accent-gold"
                animate={{ scale: [1, 1.3, 1], opacity: [1, 0, 1] }}
                transition={{ duration: 1, repeat: Infinity }}
              />
            )}
          </div>
          <span className="text-sm text-gray-400">Agent</span>
          {agentSpeaking && <span className="text-xs text-accent-gold">Speaking...</span>}
        </motion.div>
      </div>

      {/* Call Button */}
      <div className="flex justify-center">
        <AnimatePresence mode="wait">
          {!isRecording ? (
            <motion.button
              key="start"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onStartCall}
              className="flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-accent-gold to-accent-copper rounded-full text-midnight font-semibold shadow-lg hover:shadow-accent-gold/30 transition-shadow"
            >
              <Phone className="w-5 h-5" />
              Start Call
            </motion.button>
          ) : (
            <motion.button
              key="end"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onEndCall}
              className="flex items-center gap-3 px-8 py-4 bg-red-600 rounded-full text-white font-semibold shadow-lg hover:shadow-red-500/30 transition-shadow"
            >
              <PhoneOff className="w-5 h-5" />
              End Call
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Text Input (for simulation mode) */}
      {isConnected && (
        <form onSubmit={handleSubmitText} className="pt-4 border-t border-gray-700/50">
          <label className="block text-sm text-gray-400 mb-2">
            Text Input (simulation mode)
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="Type a message..."
              className="flex-1 bg-deep-purple border border-gray-700 rounded-lg px-4 py-2 text-soft-cream placeholder-gray-500 focus:border-accent-gold focus:outline-none"
            />
            <button
              type="submit"
              disabled={!textInput.trim()}
              className="px-4 py-2 bg-accent-gold/20 text-accent-gold rounded-lg hover:bg-accent-gold/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          </div>
        </form>
      )}

      {/* Demo Banner */}
      <div className="bg-amber-900/30 border border-amber-700/50 rounded-lg p-3 text-center">
        <p className="text-amber-200 text-sm">
          ⚠️ Demo System — Do not share sensitive information
        </p>
      </div>
    </div>
  );
}
