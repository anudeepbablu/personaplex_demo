"""Reservation and availability service."""
import random
import string
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Reservation, Table, Restaurant, WaitlistEntry,
    ReservationStatus, WaitlistStatus, TableArea
)


def generate_confirmation_code() -> str:
    """Generate a 6-character confirmation code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


class ReservationService:
    """Service for managing reservations and availability."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def check_availability(
        self,
        restaurant_id: int,
        date_time: datetime,
        party_size: int,
        area_pref: Optional[TableArea] = None,
        duration_min: int = 90
    ) -> Tuple[bool, Optional[dict], List[dict]]:
        """Check if requested time slot is available.
        
        Returns:
            Tuple of (is_available, slot_info, alternatives)
        """
        # Get all tables that can accommodate the party
        table_query = select(Table).where(
            and_(
                Table.restaurant_id == restaurant_id,
                Table.capacity >= party_size
            )
        )
        if area_pref:
            table_query = table_query.where(Table.area == area_pref)
        
        result = await self.db.execute(table_query)
        suitable_tables = result.scalars().all()
        
        if not suitable_tables:
            return False, None, []
        
        # Check for conflicting reservations at requested time
        end_time = date_time + timedelta(minutes=duration_min)
        
        conflict_query = select(Reservation).where(
            and_(
                Reservation.restaurant_id == restaurant_id,
                Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.CONFIRMED]),
                Reservation.start_time < end_time,
                Reservation.start_time + timedelta(minutes=90) > date_time  # Simplified overlap check
            )
        )
        
        result = await self.db.execute(conflict_query)
        conflicting_reservations = result.scalars().all()
        
        # Calculate available tables
        booked_count = len(conflicting_reservations)
        available_count = len(suitable_tables) - booked_count
        
        requested_available = available_count > 0
        
        slot_info = None
        if requested_available:
            slot_info = {
                "time": date_time,
                "area": area_pref or TableArea.INDOOR,
                "tables_available": available_count
            }
        
        # Find alternatives if requested time not available
        alternatives = []
        if not requested_available:
            # Check slots before and after
            for offset in [-30, -60, 30, 60, 90, 120]:
                alt_time = date_time + timedelta(minutes=offset)
                
                # Skip past times
                if alt_time < datetime.now():
                    continue
                
                alt_end = alt_time + timedelta(minutes=duration_min)
                alt_conflict_query = select(Reservation).where(
                    and_(
                        Reservation.restaurant_id == restaurant_id,
                        Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.CONFIRMED]),
                        Reservation.start_time < alt_end,
                        Reservation.start_time + timedelta(minutes=90) > alt_time
                    )
                )
                
                result = await self.db.execute(alt_conflict_query)
                alt_conflicts = result.scalars().all()
                alt_available = len(suitable_tables) - len(alt_conflicts)
                
                if alt_available > 0:
                    # Check different areas if original preference wasn't met
                    areas_to_check = [area_pref] if area_pref else [TableArea.INDOOR, TableArea.PATIO]
                    
                    for area in areas_to_check:
                        alternatives.append({
                            "time": alt_time,
                            "area": area,
                            "tables_available": alt_available
                        })
                
                if len(alternatives) >= 4:
                    break
        
        return requested_available, slot_info, alternatives
    
    async def create_reservation(
        self,
        restaurant_id: int,
        guest_name: str,
        phone: str,
        party_size: int,
        start_time: datetime,
        area_pref: Optional[TableArea] = None,
        notes: Optional[str] = None,
        duration_min: int = 90
    ) -> Reservation:
        """Create a new reservation."""
        confirmation_code = generate_confirmation_code()
        
        reservation = Reservation(
            restaurant_id=restaurant_id,
            guest_name=guest_name,
            phone=phone,
            party_size=party_size,
            start_time=start_time,
            duration_min=duration_min,
            area_pref=area_pref,
            notes=notes,
            status=ReservationStatus.CONFIRMED,
            confirmation_code=confirmation_code
        )
        
        self.db.add(reservation)
        await self.db.commit()
        await self.db.refresh(reservation)
        
        return reservation
    
    async def find_reservation(
        self,
        restaurant_id: int,
        confirmation_code: Optional[str] = None,
        phone: Optional[str] = None,
        guest_name: Optional[str] = None
    ) -> Optional[Reservation]:
        """Find a reservation by confirmation code, phone, or name."""
        conditions = [Reservation.restaurant_id == restaurant_id]
        
        if confirmation_code:
            conditions.append(Reservation.confirmation_code == confirmation_code.upper())
        if phone:
            conditions.append(Reservation.phone == phone)
        if guest_name:
            conditions.append(Reservation.guest_name.ilike(f"%{guest_name}%"))
        
        query = select(Reservation).where(
            and_(*conditions)
        ).order_by(Reservation.start_time.desc())
        
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def modify_reservation(
        self,
        reservation_id: int,
        **updates
    ) -> Optional[Reservation]:
        """Modify an existing reservation."""
        query = select(Reservation).where(Reservation.id == reservation_id)
        result = await self.db.execute(query)
        reservation = result.scalars().first()
        
        if not reservation:
            return None
        
        for key, value in updates.items():
            if hasattr(reservation, key) and value is not None:
                setattr(reservation, key, value)
        
        reservation.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(reservation)
        
        return reservation
    
    async def cancel_reservation(
        self,
        reservation_id: Optional[int] = None,
        confirmation_code: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Optional[Reservation]:
        """Cancel a reservation."""
        conditions = []
        
        if reservation_id:
            conditions.append(Reservation.id == reservation_id)
        if confirmation_code:
            conditions.append(Reservation.confirmation_code == confirmation_code.upper())
        if phone:
            conditions.append(Reservation.phone == phone)
        
        if not conditions:
            return None
        
        query = select(Reservation).where(and_(*conditions))
        result = await self.db.execute(query)
        reservation = result.scalars().first()
        
        if reservation:
            reservation.status = ReservationStatus.CANCELLED
            reservation.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(reservation)
        
        return reservation
    
    async def get_upcoming_reservations(
        self,
        restaurant_id: int,
        from_time: Optional[datetime] = None,
        limit: int = 20
    ) -> List[Reservation]:
        """Get upcoming reservations."""
        from_time = from_time or datetime.now()
        
        query = select(Reservation).where(
            and_(
                Reservation.restaurant_id == restaurant_id,
                Reservation.start_time >= from_time,
                Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.CONFIRMED])
            )
        ).order_by(Reservation.start_time).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()


class WaitlistService:
    """Service for managing the waitlist."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def add_to_waitlist(
        self,
        restaurant_id: int,
        guest_name: str,
        phone: str,
        party_size: int,
        notes: Optional[str] = None
    ) -> Tuple[WaitlistEntry, int, int]:
        """Add a party to the waitlist.
        
        Returns:
            Tuple of (entry, position, estimated_wait_min)
        """
        entry = WaitlistEntry(
            restaurant_id=restaurant_id,
            guest_name=guest_name,
            phone=phone,
            party_size=party_size,
            notes=notes,
            status=WaitlistStatus.WAITING
        )
        
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        
        # Calculate position
        position_query = select(WaitlistEntry).where(
            and_(
                WaitlistEntry.restaurant_id == restaurant_id,
                WaitlistEntry.status == WaitlistStatus.WAITING,
                WaitlistEntry.created_at <= entry.created_at
            )
        )
        result = await self.db.execute(position_query)
        position = len(result.scalars().all())
        
        # Estimate wait (roughly 15 min per party ahead)
        estimated_wait = position * 15
        
        return entry, position, estimated_wait
    
    async def get_waitlist_position(
        self,
        entry_id: int
    ) -> Tuple[Optional[WaitlistEntry], int, int]:
        """Get current position in waitlist."""
        query = select(WaitlistEntry).where(WaitlistEntry.id == entry_id)
        result = await self.db.execute(query)
        entry = result.scalars().first()
        
        if not entry or entry.status != WaitlistStatus.WAITING:
            return entry, 0, 0
        
        position_query = select(WaitlistEntry).where(
            and_(
                WaitlistEntry.restaurant_id == entry.restaurant_id,
                WaitlistEntry.status == WaitlistStatus.WAITING,
                WaitlistEntry.created_at <= entry.created_at
            )
        )
        result = await self.db.execute(position_query)
        position = len(result.scalars().all())
        
        estimated_wait = position * 15
        
        return entry, position, estimated_wait
    
    async def remove_from_waitlist(
        self,
        entry_id: int,
        status: WaitlistStatus = WaitlistStatus.CANCELLED
    ) -> Optional[WaitlistEntry]:
        """Remove entry from waitlist."""
        query = select(WaitlistEntry).where(WaitlistEntry.id == entry_id)
        result = await self.db.execute(query)
        entry = result.scalars().first()
        
        if entry:
            entry.status = status
            await self.db.commit()
            await self.db.refresh(entry)
        
        return entry
