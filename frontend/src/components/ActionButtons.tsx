import { motion } from 'framer-motion';
import {
  CheckCircle, Edit3, XCircle, Clock, MessageSquare, Send
} from 'lucide-react';
import type { ExtractedFields } from '../types';

interface ActionButtonsProps {
  fields: ExtractedFields;
  missingFields: string[];
  currentState: string;
  onConfirm: () => void;
  onModify: () => void;
  onCancel: () => void;
  onWaitlist: () => void;
  onSendSMS: () => void;
}

export function ActionButtons({
  fields,
  missingFields,
  currentState,
  onConfirm,
  onModify,
  onCancel,
  onWaitlist,
  onSendSMS,
}: ActionButtonsProps) {
  const canConfirm = missingFields.length === 0 && fields.intent === 'reserve';
  const isComplete = currentState === 'complete';

  return (
    <div className="glass rounded-2xl p-6 space-y-4">
      <h2 className="font-display text-xl text-accent-gold">Actions</h2>

      <div className="grid grid-cols-2 gap-3">
        {/* Confirm Reservation */}
        <motion.button
          whileHover={{ scale: canConfirm ? 1.02 : 1 }}
          whileTap={{ scale: canConfirm ? 0.98 : 1 }}
          onClick={onConfirm}
          disabled={!canConfirm}
          className={`flex items-center justify-center gap-2 p-4 rounded-xl font-medium transition-all ${
            canConfirm
              ? 'bg-gradient-to-r from-green-600 to-emerald-500 text-white shadow-lg hover:shadow-green-500/30'
              : 'bg-gray-700/50 text-gray-500 cursor-not-allowed'
          }`}
        >
          <CheckCircle className="w-5 h-5" />
          Confirm
        </motion.button>

        {/* Add to Waitlist */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onWaitlist}
          className="flex items-center justify-center gap-2 p-4 rounded-xl font-medium bg-amber-600/20 text-amber-400 border border-amber-600/50 hover:bg-amber-600/30 transition-all"
        >
          <Clock className="w-5 h-5" />
          Waitlist
        </motion.button>

        {/* Modify */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onModify}
          className="flex items-center justify-center gap-2 p-4 rounded-xl font-medium bg-blue-600/20 text-blue-400 border border-blue-600/50 hover:bg-blue-600/30 transition-all"
        >
          <Edit3 className="w-5 h-5" />
          Modify
        </motion.button>

        {/* Cancel */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onCancel}
          className="flex items-center justify-center gap-2 p-4 rounded-xl font-medium bg-red-600/20 text-red-400 border border-red-600/50 hover:bg-red-600/30 transition-all"
        >
          <XCircle className="w-5 h-5" />
          Cancel
        </motion.button>
      </div>

      {/* SMS Confirmation */}
      {isComplete && fields.phone && (
        <motion.button
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onSendSMS}
          className="w-full flex items-center justify-center gap-2 p-4 rounded-xl font-medium bg-gradient-to-r from-accent-gold to-accent-copper text-midnight shadow-lg hover:shadow-accent-gold/30 transition-all"
        >
          <Send className="w-5 h-5" />
          Send SMS Confirmation
        </motion.button>
      )}

      {/* Status Message */}
      <div className="p-3 bg-deep-purple/50 rounded-lg border border-gray-700/50">
        {missingFields.length > 0 ? (
          <p className="text-sm text-gray-400">
            <span className="text-amber-400">Waiting for:</span>{' '}
            {missingFields.map(f => f.replace('_', ' ')).join(', ')}
          </p>
        ) : canConfirm ? (
          <p className="text-sm text-green-400">
            ✓ All required information collected. Ready to confirm!
          </p>
        ) : isComplete ? (
          <p className="text-sm text-accent-gold">
            ✓ Reservation complete!
          </p>
        ) : (
          <p className="text-sm text-gray-400">
            Listening for reservation details...
          </p>
        )}
      </div>
    </div>
  );
}
