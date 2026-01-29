import { motion } from 'framer-motion';
import { Calendar, Clock, MapPin, Users } from 'lucide-react';
import type { TimeSlot } from '../types';

interface AvailabilityPanelProps {
  slots: TimeSlot[];
  selectedSlot: TimeSlot | null;
  onSelectSlot: (slot: TimeSlot) => void;
}

const AREA_ICONS: Record<string, string> = {
  indoor: '🏠',
  patio: '🌳',
  bar: '🍸',
  private: '🚪',
};

export function AvailabilityPanel({
  slots,
  selectedSlot,
  onSelectSlot,
}: AvailabilityPanelProps) {
  const formatTime = (timeStr: string) => {
    const date = new Date(timeStr);
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  };

  const formatDate = (timeStr: string) => {
    const date = new Date(timeStr);
    return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  };

  // Group slots by date
  const slotsByDate = slots.reduce((acc, slot) => {
    const dateKey = formatDate(slot.time);
    if (!acc[dateKey]) acc[dateKey] = [];
    acc[dateKey].push(slot);
    return acc;
  }, {} as Record<string, TimeSlot[]>);

  return (
    <div className="glass rounded-2xl p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Calendar className="w-5 h-5 text-accent-gold" />
        <h2 className="font-display text-xl text-accent-gold">Availability</h2>
      </div>

      {slots.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <Clock className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>Availability will appear here</p>
          <p className="text-sm mt-1">Ask about times to see options</p>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.entries(slotsByDate).map(([date, dateSlots]) => (
            <div key={date}>
              <h3 className="text-sm font-medium text-gray-400 mb-2">{date}</h3>
              <div className="grid grid-cols-2 gap-2">
                {dateSlots.map((slot, index) => {
                  const isSelected = selectedSlot?.time === slot.time && selectedSlot?.area === slot.area;

                  return (
                    <motion.button
                      key={`${slot.time}-${slot.area}-${index}`}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => onSelectSlot(slot)}
                      className={`p-3 rounded-xl text-left transition-all ${
                        isSelected
                          ? 'bg-accent-gold/20 border-2 border-accent-gold'
                          : 'bg-deep-purple border border-gray-700 hover:border-gray-600'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className={`font-medium ${isSelected ? 'text-accent-gold' : 'text-soft-cream'}`}>
                          {formatTime(slot.time)}
                        </span>
                        <span className="text-lg">{AREA_ICONS[slot.area] || '🍽️'}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <MapPin className="w-3 h-3" />
                        <span className="capitalize">{slot.area}</span>
                        <span className="text-gray-600">•</span>
                        <Users className="w-3 h-3" />
                        <span>{slot.tables_available} tables</span>
                      </div>
                    </motion.button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="pt-4 border-t border-gray-700/50">
        <p className="text-xs text-gray-500 mb-2">Seating Areas</p>
        <div className="flex flex-wrap gap-3">
          {Object.entries(AREA_ICONS).map(([area, icon]) => (
            <span key={area} className="text-sm text-gray-400">
              {icon} {area.charAt(0).toUpperCase() + area.slice(1)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
