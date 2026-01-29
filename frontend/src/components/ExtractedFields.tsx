import { motion } from 'framer-motion';
import {
  User, Phone, Users, Calendar, MapPin, FileText,
  CheckCircle, AlertCircle, Clock
} from 'lucide-react';
import type { ExtractedFields as ExtractedFieldsType, IntentType } from '../types';

interface ExtractedFieldsProps {
  fields: ExtractedFieldsType;
  missingFields: string[];
}

const INTENT_LABELS: Record<IntentType, { label: string; color: string }> = {
  reserve: { label: 'Make Reservation', color: 'bg-green-500' },
  modify: { label: 'Modify Reservation', color: 'bg-blue-500' },
  cancel: { label: 'Cancel Reservation', color: 'bg-red-500' },
  faq: { label: 'Question', color: 'bg-purple-500' },
  waitlist: { label: 'Join Waitlist', color: 'bg-orange-500' },
};

const AREA_LABELS: Record<string, string> = {
  indoor: '🏠 Indoor',
  patio: '🌳 Patio',
  bar: '🍸 Bar',
  private: '🚪 Private Room',
};

export function ExtractedFields({ fields, missingFields }: ExtractedFieldsProps) {
  const formatDateTime = (dateTime: string | null) => {
    if (!dateTime) return null;
    const date = new Date(dateTime);
    return {
      date: date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }),
      time: date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }),
    };
  };

  const dateTime = formatDateTime(fields.date_time);

  const fieldItems = [
    {
      key: 'guest_name',
      icon: User,
      label: 'Name',
      value: fields.guest_name,
    },
    {
      key: 'phone',
      icon: Phone,
      label: 'Phone',
      value: fields.phone ? formatPhone(fields.phone) : null,
    },
    {
      key: 'party_size',
      icon: Users,
      label: 'Party Size',
      value: fields.party_size ? `${fields.party_size} guests` : null,
    },
    {
      key: 'date_time',
      icon: Calendar,
      label: 'Date & Time',
      value: dateTime ? `${dateTime.date} at ${dateTime.time}` : null,
    },
    {
      key: 'area_pref',
      icon: MapPin,
      label: 'Seating',
      value: fields.area_pref ? AREA_LABELS[fields.area_pref] || fields.area_pref : null,
    },
    {
      key: 'notes',
      icon: FileText,
      label: 'Notes',
      value: fields.notes,
    },
  ];

  return (
    <div className="glass rounded-2xl p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl text-accent-gold">Reservation Details</h2>
        {fields.intent && INTENT_LABELS[fields.intent] && (
          <span className={`px-3 py-1 rounded-full text-xs font-medium text-white ${INTENT_LABELS[fields.intent].color}`}>
            {INTENT_LABELS[fields.intent].label}
          </span>
        )}
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-400">Completion</span>
          <span className="text-accent-gold">
            {fieldItems.filter(f => f.value && !['notes', 'area_pref'].includes(f.key)).length} / 4 required
          </span>
        </div>
        <div className="h-2 bg-deep-purple rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-accent-gold to-accent-copper"
            initial={{ width: 0 }}
            animate={{
              width: `${(fieldItems.filter(f => f.value && !['notes', 'area_pref'].includes(f.key)).length / 4) * 100}%`
            }}
            transition={{ duration: 0.5 }}
          />
        </div>
      </div>

      {/* Fields */}
      <div className="space-y-3">
        {fieldItems.map((item) => {
          const isMissing = missingFields.includes(item.key);
          const isRequired = ['guest_name', 'phone', 'party_size', 'date_time'].includes(item.key);
          const Icon = item.icon;

          return (
            <motion.div
              key={item.key}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className={`flex items-center gap-3 p-3 rounded-lg transition-colors ${
                item.value
                  ? 'bg-accent-gold/10 border border-accent-gold/30'
                  : isMissing && isRequired
                  ? 'bg-red-900/20 border border-red-700/30'
                  : 'bg-deep-purple border border-gray-700/50'
              }`}
            >
              {/* Icon */}
              <div className={`p-2 rounded-lg ${
                item.value ? 'bg-accent-gold/20' : 'bg-gray-700/50'
              }`}>
                <Icon className={`w-4 h-4 ${
                  item.value ? 'text-accent-gold' : 'text-gray-500'
                }`} />
              </div>

              {/* Label & Value */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">{item.label}</span>
                  {isRequired && !item.value && (
                    <span className="text-xs text-red-400">required</span>
                  )}
                </div>
                {item.value ? (
                  <p className="text-soft-cream font-medium truncate">{item.value}</p>
                ) : (
                  <p className="text-gray-600 text-sm italic">Not provided</p>
                )}
              </div>

              {/* Status Icon */}
              {item.value ? (
                <CheckCircle className="w-5 h-5 text-green-500" />
              ) : isMissing && isRequired ? (
                <AlertCircle className="w-5 h-5 text-red-400" />
              ) : (
                <Clock className="w-5 h-5 text-gray-600" />
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Confirmation Code */}
      {fields.confirmation_code && (
        <div className="mt-4 p-4 bg-accent-gold/10 border border-accent-gold/30 rounded-lg">
          <span className="text-sm text-gray-400">Confirmation Code</span>
          <p className="text-2xl font-mono text-accent-gold font-bold tracking-wider">
            {fields.confirmation_code}
          </p>
        </div>
      )}
    </div>
  );
}

function formatPhone(phone: string): string {
  const cleaned = phone.replace(/\D/g, '');
  if (cleaned.length === 10) {
    return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
  }
  return phone;
}
