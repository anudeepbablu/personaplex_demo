import { motion } from 'framer-motion';
import { Sparkles, Volume2, ChefHat, Home, Trophy } from 'lucide-react';
import type { PersonaType } from '../types';
import { PERSONAS, VOICES } from '../types';

interface PersonaControlsProps {
  currentPersona: PersonaType;
  currentVoice: string;
  onPersonaChange: (persona: PersonaType) => void;
  onVoiceChange: (voice: string) => void;
}

const PERSONA_ICONS: Record<PersonaType, typeof ChefHat> = {
  fine_dining: ChefHat,
  family: Home,
  sports_bar: Trophy,
};

const PERSONA_GRADIENTS: Record<PersonaType, string> = {
  fine_dining: 'from-amber-600 to-yellow-500',
  family: 'from-emerald-500 to-teal-400',
  sports_bar: 'from-orange-500 to-red-500',
};

export function PersonaControls({
  currentPersona,
  currentVoice,
  onPersonaChange,
  onVoiceChange,
}: PersonaControlsProps) {
  return (
    <div className="glass rounded-2xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-accent-gold" />
        <h2 className="font-display text-xl text-accent-gold">Persona & Voice</h2>
      </div>

      {/* Persona Selection */}
      <div className="space-y-3">
        <label className="text-sm text-gray-400 font-medium">Restaurant Style</label>
        <div className="grid grid-cols-1 gap-2">
          {PERSONAS.map((persona) => {
            const Icon = PERSONA_ICONS[persona.id];
            const isSelected = currentPersona === persona.id;

            return (
              <motion.button
                key={persona.id}
                onClick={() => onPersonaChange(persona.id)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`relative flex items-center gap-3 p-4 rounded-xl transition-all ${
                  isSelected
                    ? 'bg-gradient-to-r ' + PERSONA_GRADIENTS[persona.id] + ' text-white shadow-lg'
                    : 'bg-deep-purple border border-gray-700 hover:border-gray-600'
                }`}
              >
                <div className={`p-2 rounded-lg ${
                  isSelected ? 'bg-white/20' : 'bg-gray-700/50'
                }`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="text-left">
                  <p className="font-medium">{persona.name}</p>
                  <p className={`text-xs ${isSelected ? 'text-white/80' : 'text-gray-500'}`}>
                    {persona.restaurant_type}
                  </p>
                </div>
                {isSelected && (
                  <motion.div
                    layoutId="persona-indicator"
                    className="absolute right-4 w-2 h-2 rounded-full bg-white"
                  />
                )}
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* Voice Selection */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-gray-400" />
          <label className="text-sm text-gray-400 font-medium">Voice</label>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {VOICES.map((voice) => {
            const isSelected = currentVoice === voice.id;

            return (
              <motion.button
                key={voice.id}
                onClick={() => onVoiceChange(voice.id)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`p-3 rounded-lg text-left transition-all ${
                  isSelected
                    ? 'bg-accent-gold/20 border-2 border-accent-gold'
                    : 'bg-deep-purple border border-gray-700 hover:border-gray-600'
                }`}
              >
                <p className={`font-mono text-sm ${isSelected ? 'text-accent-gold' : 'text-gray-300'}`}>
                  {voice.id}
                </p>
                <p className="text-xs text-gray-500 mt-1">{voice.description}</p>
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* Voice Preview Info */}
      <div className="p-3 bg-deep-purple/50 rounded-lg border border-gray-700/50">
        <p className="text-xs text-gray-400">
          💡 Switch personas mid-call to hear the tone change while maintaining context.
        </p>
      </div>
    </div>
  );
}
