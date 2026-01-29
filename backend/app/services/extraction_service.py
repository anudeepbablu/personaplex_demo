"""Service for extracting structured information from transcripts."""
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from app.session_manager import ExtractedInfo, ConversationState


class ExtractionService:
    """Extract structured information from conversation transcripts."""
    
    # Common patterns
    PHONE_PATTERNS = [
        r'\b(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\b',  # 555-123-4567
        r'\b(\(\d{3}\)\s*\d{3}[-.\s]?\d{4})\b',  # (555) 123-4567
        r'\b(\d{10})\b',  # 5551234567
    ]
    
    PARTY_SIZE_PATTERNS = [
        r'\b(?:party of|table for|for)\s*(\d+)\b',
        r'\b(\d+)\s*(?:people|guests|of us|persons)\b',
        r'\bjust\s*(\d+)\b',
        r'\b(two|three|four|five|six|seven|eight|nine|ten)\b',
    ]
    
    NUMBER_WORDS = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12
    }
    
    TIME_PATTERNS = [
        r'\b(\d{1,2})\s*(?::|\.)?(\d{2})?\s*(am|pm|a\.m\.|p\.m\.)\b',
        r'\b(\d{1,2})\s*(?:o\'?clock)?\s*(am|pm|a\.m\.|p\.m\.)?\b',
        r'\b(noon|midnight)\b',
    ]
    
    DATE_PATTERNS = [
        r'\b(today|tonight|tomorrow)\b',
        r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
        r'\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b',
    ]
    
    AREA_KEYWORDS = {
        'indoor': ['inside', 'indoor', 'indoors', 'main dining', 'interior'],
        'patio': ['patio', 'outside', 'outdoor', 'outdoors', 'terrace', 'garden'],
        'bar': ['bar', 'lounge', 'bar area', 'bar seating'],
        'private': ['private', 'private room', 'private dining'],
    }
    
    INTENT_KEYWORDS = {
        'reserve': ['reservation', 'reserve', 'book', 'booking', 'table for', 'make a'],
        'modify': ['change', 'modify', 'update', 'reschedule', 'move'],
        'cancel': ['cancel', 'cancellation', 'delete', 'remove'],
        'waitlist': ['waitlist', 'wait list', 'waiting list', 'walk-in', 'walk in'],
        'faq': ['hours', 'parking', 'menu', 'dress code', 'policy', 'allergies', 'gluten', 'vegan'],
    }
    
    def __init__(self):
        pass
    
    def extract_from_text(self, text: str, current_info: ExtractedInfo) -> ExtractedInfo:
        """Extract information from a single utterance.
        
        Args:
            text: The text to extract from
            current_info: Current extracted information to update
            
        Returns:
            Updated ExtractedInfo
        """
        text_lower = text.lower()
        
        # Extract intent if not already set
        if not current_info.intent:
            current_info.intent = self._extract_intent(text_lower)
        
        # Extract phone number
        phone = self._extract_phone(text)
        if phone:
            current_info.phone = phone
        
        # Extract party size
        party_size = self._extract_party_size(text_lower)
        if party_size:
            current_info.party_size = party_size
        
        # Extract date/time
        date_time = self._extract_datetime(text_lower)
        if date_time:
            current_info.date_time = date_time
        
        # Extract area preference
        area = self._extract_area(text_lower)
        if area:
            current_info.area_pref = area
        
        # Extract name (look for "my name is" or "name's" patterns)
        name = self._extract_name(text)
        if name:
            current_info.guest_name = name
        
        # Extract special notes (allergies, occasions)
        notes = self._extract_notes(text_lower)
        if notes:
            if current_info.notes:
                current_info.notes += f"; {notes}"
            else:
                current_info.notes = notes
        
        # Extract confirmation code for modify/cancel
        conf_code = self._extract_confirmation_code(text)
        if conf_code:
            current_info.confirmation_code = conf_code
        
        return current_info
    
    def _extract_intent(self, text: str) -> Optional[str]:
        """Detect the user's intent."""
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return intent
        return None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number from text."""
        for pattern in self.PHONE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                # Normalize to digits only
                phone = re.sub(r'\D', '', match.group(1))
                if len(phone) == 10:
                    return phone
        return None
    
    def _extract_party_size(self, text: str) -> Optional[int]:
        """Extract party size from text."""
        for pattern in self.PARTY_SIZE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                size_str = match.group(1).lower()
                if size_str in self.NUMBER_WORDS:
                    return self.NUMBER_WORDS[size_str]
                try:
                    return int(size_str)
                except ValueError:
                    continue
        return None
    
    def _extract_datetime(self, text: str) -> Optional[datetime]:
        """Extract date and time from text."""
        now = datetime.now()
        target_date = None
        target_time = None
        
        # Extract date
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(0).lower()
                
                if 'today' in date_str or 'tonight' in date_str:
                    target_date = now.date()
                elif 'tomorrow' in date_str:
                    target_date = (now + timedelta(days=1)).date()
                elif any(day in date_str for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
                    # Find next occurrence of the day
                    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                    for i, day in enumerate(days):
                        if day in date_str:
                            days_ahead = i - now.weekday()
                            if 'next' in date_str:
                                days_ahead += 7
                            elif days_ahead <= 0:
                                days_ahead += 7
                            target_date = (now + timedelta(days=days_ahead)).date()
                            break
                break
        
        # Extract time
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if groups[0] in ['noon', 'midnight']:
                    hour = 12 if groups[0] == 'noon' else 0
                    minute = 0
                else:
                    hour = int(groups[0])
                    minute = int(groups[1]) if groups[1] else 0
                    
                    # Handle AM/PM
                    period = groups[-1].lower() if groups[-1] else None
                    if period and ('pm' in period or 'p.m.' in period):
                        if hour != 12:
                            hour += 12
                    elif period and ('am' in period or 'a.m.' in period):
                        if hour == 12:
                            hour = 0
                    elif hour < 9:  # Assume PM for restaurant hours
                        hour += 12
                
                target_time = (hour, minute)
                break
        
        # Combine date and time
        if target_date and target_time:
            return datetime.combine(target_date, datetime.min.time().replace(
                hour=target_time[0], minute=target_time[1]
            ))
        elif target_time and not target_date:
            # Assume today if only time given
            return datetime.combine(now.date(), datetime.min.time().replace(
                hour=target_time[0], minute=target_time[1]
            ))
        
        return None
    
    def _extract_area(self, text: str) -> Optional[str]:
        """Extract seating area preference."""
        for area, keywords in self.AREA_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return area
        return None
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract guest name from text."""
        patterns = [
            r"(?:my name is|name's|this is|i'm|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(?:under|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(?:it's|its)\s+([A-Z][a-z]+)\s+(?:here|calling)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Basic validation - should have at least 2 chars
                if len(name) >= 2:
                    return name.title()
        
        return None
    
    def _extract_notes(self, text: str) -> Optional[str]:
        """Extract special notes (allergies, occasions, etc.)."""
        notes = []
        
        # Allergies
        allergy_patterns = [
            r'(?:allergic to|allergy to|can\'t have|no)\s+(\w+)',
            r'(\w+)\s+(?:allergy|allergies|intolerance)',
        ]
        for pattern in allergy_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if match.lower() not in ['a', 'an', 'the', 'any']:
                    notes.append(f"Allergy: {match}")
        
        # Special occasions
        occasions = ['birthday', 'anniversary', 'celebration', 'proposal', 'engagement']
        for occasion in occasions:
            if occasion in text:
                notes.append(f"Occasion: {occasion}")
        
        # Accessibility
        accessibility = ['wheelchair', 'accessible', 'mobility', 'walker']
        for access in accessibility:
            if access in text:
                notes.append("Accessibility needed")
                break
        
        # High chair / kids
        if 'high chair' in text or 'highchair' in text:
            notes.append("High chair needed")
        if 'booster' in text:
            notes.append("Booster seat needed")
        
        return "; ".join(notes) if notes else None
    
    def _extract_confirmation_code(self, text: str) -> Optional[str]:
        """Extract confirmation code from text."""
        # Look for 6-character alphanumeric codes
        pattern = r'\b([A-Z0-9]{6})\b'
        match = re.search(pattern, text.upper())
        if match:
            return match.group(1)
        return None
    
    def determine_next_state(
        self,
        current_state: ConversationState,
        extracted: ExtractedInfo
    ) -> ConversationState:
        """Determine the next conversation state based on extracted info."""
        
        if current_state == ConversationState.GREETING:
            if extracted.intent:
                if extracted.intent == 'faq':
                    return ConversationState.FAQ_MODE
                elif extracted.intent == 'cancel':
                    return ConversationState.CANCEL_FLOW
                elif extracted.intent == 'modify':
                    return ConversationState.MODIFY_FLOW
                elif extracted.intent == 'waitlist':
                    return ConversationState.WAITLIST_FLOW
                else:
                    return ConversationState.COLLECTING_RESERVATION
            return ConversationState.IDENTIFY_INTENT
        
        if current_state == ConversationState.IDENTIFY_INTENT:
            if extracted.intent == 'faq':
                return ConversationState.FAQ_MODE
            elif extracted.intent == 'cancel':
                return ConversationState.CANCEL_FLOW
            elif extracted.intent == 'modify':
                return ConversationState.MODIFY_FLOW
            elif extracted.intent == 'waitlist':
                return ConversationState.WAITLIST_FLOW
            return ConversationState.COLLECTING_RESERVATION
        
        if current_state == ConversationState.COLLECTING_RESERVATION:
            missing = extracted.get_missing_fields()
            if not missing:
                return ConversationState.CHECKING_AVAILABILITY
        
        if current_state == ConversationState.CHECKING_AVAILABILITY:
            # This would be set by the availability check result
            return ConversationState.CONFIRMING
        
        if current_state == ConversationState.OFFERING_ALTERNATIVES:
            # User accepted an alternative
            return ConversationState.CONFIRMING
        
        if current_state == ConversationState.CONFIRMING:
            return ConversationState.COMPLETE
        
        return current_state
    
    def get_next_question(self, extracted: ExtractedInfo) -> Optional[str]:
        """Suggest what to ask next based on missing fields."""
        missing = extracted.get_missing_fields()
        
        if not missing:
            return None
        
        prompts = {
            'date_time': "What date and time would you like to come in?",
            'party_size': "How many people will be in your party?",
            'guest_name': "May I have a name for the reservation?",
            'phone': "And what's the best phone number to reach you?",
        }
        
        # Prioritized order
        priority = ['date_time', 'party_size', 'guest_name', 'phone']
        
        for field in priority:
            if field in missing:
                return prompts[field]
        
        return None
