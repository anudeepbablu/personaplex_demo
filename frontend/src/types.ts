// Session types
export interface Session {
  session_id: string;
  restaurant_id: number;
  created_at: string;
  persona_type: PersonaType;
  voice_id: string;
  state: ConversationState;
  extracted: ExtractedFields;
  transcript: TranscriptEntry[];
  facts: string[];
  missing_fields: string[];
  is_active: boolean;
  user_speaking: boolean;
  agent_speaking: boolean;
}

export type PersonaType = 'fine_dining' | 'family' | 'sports_bar';

export type ConversationState =
  | 'greeting'
  | 'identify_intent'
  | 'collecting_reservation'
  | 'checking_availability'
  | 'offering_alternatives'
  | 'confirming'
  | 'complete'
  | 'faq_mode'
  | 'modify_flow'
  | 'cancel_flow'
  | 'waitlist_flow';

export interface ExtractedFields {
  guest_name: string | null;
  phone: string | null;
  party_size: number | null;
  date_time: string | null;
  area_pref: AreaType | null;
  notes: string | null;
  intent: IntentType | null;
  confirmation_code: string | null;
}

export type AreaType = 'indoor' | 'patio' | 'bar' | 'private';

export type IntentType = 'reserve' | 'modify' | 'cancel' | 'faq' | 'waitlist';

export interface TranscriptEntry {
  speaker: 'user' | 'agent';
  text: string;
  timestamp: string;
  confidence?: number;
}

// Reservation types
export interface TimeSlot {
  time: string;
  area: AreaType;
  tables_available: number;
}

export interface Reservation {
  id: number;
  confirmation_code: string;
  guest_name: string;
  phone: string;
  party_size: number;
  start_time: string;
  area_pref: AreaType | null;
  notes: string | null;
  status: ReservationStatus;
}

export type ReservationStatus = 'pending' | 'confirmed' | 'cancelled' | 'completed' | 'no_show';

// WebSocket message types
export interface WSMessage {
  type: string;
  data?: any;
  [key: string]: any;
}

export interface SpeakingState {
  user_speaking: boolean;
  agent_speaking: boolean;
}

// Voice and Persona config
export interface VoiceConfig {
  id: string;
  name: string;
  description: string;
}

export interface PersonaConfig {
  id: PersonaType;
  name: string;
  restaurant_type: string;
  default_voice: string;
}

export const PERSONAS: PersonaConfig[] = [
  { id: 'fine_dining', name: 'Fine Dining', restaurant_type: 'Upscale fine dining', default_voice: 'NATF2' },
  { id: 'family', name: 'Family Restaurant', restaurant_type: 'Family-friendly', default_voice: 'NATF1' },
  { id: 'sports_bar', name: 'Sports Bar', restaurant_type: 'Lively sports bar', default_voice: 'NATM1' },
];

export const VOICES: VoiceConfig[] = [
  { id: 'NATF0', name: 'Natural Female 0', description: 'Warm, professional' },
  { id: 'NATF1', name: 'Natural Female 1', description: 'Friendly, upbeat' },
  { id: 'NATF2', name: 'Natural Female 2', description: 'Calm, sophisticated' },
  { id: 'NATM0', name: 'Natural Male 0', description: 'Professional, clear' },
  { id: 'NATM1', name: 'Natural Male 1', description: 'Friendly, casual' },
  { id: 'NATM2', name: 'Natural Male 2', description: 'Deep, authoritative' },
];
