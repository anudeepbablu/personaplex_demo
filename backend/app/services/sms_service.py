"""SMS notification service (with Twilio or simulated)."""
import logging
from typing import Optional
from datetime import datetime
from app.config import get_settings
from app.models import Reservation

logger = logging.getLogger(__name__)
settings = get_settings()


class SMSService:
    """Service for sending SMS notifications."""
    
    def __init__(self):
        self.enabled = bool(
            settings.twilio_account_sid and 
            settings.twilio_auth_token and 
            settings.twilio_phone_number
        )
        self.client = None
        
        if self.enabled:
            try:
                from twilio.rest import Client
                self.client = Client(
                    settings.twilio_account_sid,
                    settings.twilio_auth_token
                )
            except ImportError:
                logger.warning("Twilio library not installed. SMS will be simulated.")
                self.enabled = False
    
    async def send_confirmation(self, reservation: Reservation) -> dict:
        """Send reservation confirmation SMS."""
        message = self._build_confirmation_message(reservation)
        return await self._send_sms(reservation.phone, message)
    
    async def send_reminder(self, reservation: Reservation) -> dict:
        """Send reservation reminder SMS."""
        message = self._build_reminder_message(reservation)
        return await self._send_sms(reservation.phone, message)
    
    async def send_cancellation(self, reservation: Reservation) -> dict:
        """Send cancellation confirmation SMS."""
        message = self._build_cancellation_message(reservation)
        return await self._send_sms(reservation.phone, message)
    
    async def send_waitlist_ready(
        self,
        guest_name: str,
        phone: str,
        restaurant_name: str
    ) -> dict:
        """Send waitlist ready notification."""
        message = (
            f"Hi {guest_name}! Great news - your table at {restaurant_name} "
            f"is ready! Please check in with the host within 10 minutes."
        )
        return await self._send_sms(phone, message)
    
    async def send_custom(self, phone: str, message: str) -> dict:
        """Send a custom SMS message."""
        return await self._send_sms(phone, message)
    
    def _build_confirmation_message(self, reservation: Reservation) -> str:
        """Build confirmation message text."""
        time_str = reservation.start_time.strftime("%A, %B %d at %I:%M %p")
        area_str = f" ({reservation.area_pref.value})" if reservation.area_pref else ""
        
        return (
            f"Confirmed! Reservation for {reservation.party_size} on {time_str}{area_str}. "
            f"Confirmation code: {reservation.confirmation_code}. "
            f"We look forward to seeing you, {reservation.guest_name}!"
        )
    
    def _build_reminder_message(self, reservation: Reservation) -> str:
        """Build reminder message text."""
        time_str = reservation.start_time.strftime("%I:%M %p")
        
        return (
            f"Reminder: Your reservation for {reservation.party_size} is today at {time_str}. "
            f"Confirmation: {reservation.confirmation_code}. See you soon!"
        )
    
    def _build_cancellation_message(self, reservation: Reservation) -> str:
        """Build cancellation confirmation message."""
        return (
            f"Your reservation ({reservation.confirmation_code}) has been cancelled. "
            f"We hope to see you another time!"
        )
    
    async def _send_sms(self, phone: str, message: str) -> dict:
        """Send SMS via Twilio or simulate."""
        # Format phone number
        formatted_phone = self._format_phone(phone)
        
        if self.enabled and self.client:
            try:
                twilio_message = self.client.messages.create(
                    body=message,
                    from_=settings.twilio_phone_number,
                    to=formatted_phone
                )
                return {
                    "success": True,
                    "message_sid": twilio_message.sid,
                    "error": None
                }
            except Exception as e:
                logger.error(f"Twilio SMS error: {e}")
                return {
                    "success": False,
                    "message_sid": None,
                    "error": str(e)
                }
        else:
            # Simulated SMS
            logger.info(f"[SIMULATED SMS] To: {formatted_phone}\nMessage: {message}")
            return {
                "success": True,
                "message_sid": f"SIM_{datetime.utcnow().timestamp()}",
                "error": None,
                "simulated": True
            }
    
    def _format_phone(self, phone: str) -> str:
        """Format phone number for Twilio (E.164 format)."""
        # Remove non-digits
        digits = ''.join(filter(str.isdigit, phone))
        
        # Assume US number if 10 digits
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+{digits}"
        
        return f"+{digits}"
