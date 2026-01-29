"""Reservation and waitlist API endpoints."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.reservation_service import ReservationService, WaitlistService
from app.services.sms_service import SMSService
from app.models import TableArea
from app.schemas import (
    AvailabilityCheck, AvailabilityResponse, TimeSlot,
    ReservationCreate, ReservationModify, ReservationCancel, ReservationResponse,
    WaitlistAdd, WaitlistResponse,
    SMSNotification, SMSResponse
)

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("/check", response_model=AvailabilityResponse)
async def check_availability(
    request: AvailabilityCheck,
    db: AsyncSession = Depends(get_db)
):
    """Check availability for a reservation."""
    service = ReservationService(db)
    
    is_available, slot_info, alternatives = await service.check_availability(
        restaurant_id=1,  # Demo restaurant
        date_time=request.date_time,
        party_size=request.party_size,
        area_pref=request.area_pref
    )
    
    requested_slot = None
    if slot_info:
        requested_slot = TimeSlot(
            time=slot_info["time"],
            area=slot_info["area"],
            tables_available=slot_info["tables_available"]
        )
    
    alt_slots = [
        TimeSlot(
            time=alt["time"],
            area=alt["area"],
            tables_available=alt["tables_available"]
        )
        for alt in alternatives
    ]
    
    return AvailabilityResponse(
        requested_available=is_available,
        requested_slot=requested_slot,
        alternatives=alt_slots
    )


@router.post("/create", response_model=ReservationResponse)
async def create_reservation(
    request: ReservationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new reservation."""
    service = ReservationService(db)
    
    # Check availability first
    is_available, _, _ = await service.check_availability(
        restaurant_id=1,
        date_time=request.start_time,
        party_size=request.party_size,
        area_pref=request.area_pref
    )
    
    if not is_available:
        raise HTTPException(
            status_code=409,
            detail="Requested time slot is not available"
        )
    
    reservation = await service.create_reservation(
        restaurant_id=1,
        guest_name=request.guest_name,
        phone=request.phone,
        party_size=request.party_size,
        start_time=request.start_time,
        area_pref=request.area_pref,
        notes=request.notes
    )
    
    return ReservationResponse.model_validate(reservation)


@router.post("/modify", response_model=ReservationResponse)
async def modify_reservation(
    request: ReservationModify,
    db: AsyncSession = Depends(get_db)
):
    """Modify an existing reservation."""
    service = ReservationService(db)
    
    # Find the reservation first
    reservation = None
    if request.reservation_id:
        reservation = await service.find_reservation(
            restaurant_id=1,
            confirmation_code=None,
            phone=None
        )
        # Direct query by ID
        from sqlalchemy import select
        from app.models import Reservation
        result = await db.execute(
            select(Reservation).where(Reservation.id == request.reservation_id)
        )
        reservation = result.scalars().first()
    elif request.confirmation_code:
        reservation = await service.find_reservation(
            restaurant_id=1,
            confirmation_code=request.confirmation_code
        )
    
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    # Check new availability if time/size changed
    new_time = request.start_time or reservation.start_time
    new_size = request.party_size or reservation.party_size
    new_area = request.area_pref or reservation.area_pref
    
    if request.start_time or request.party_size:
        is_available, _, _ = await service.check_availability(
            restaurant_id=1,
            date_time=new_time,
            party_size=new_size,
            area_pref=new_area
        )
        if not is_available:
            raise HTTPException(
                status_code=409,
                detail="New time slot is not available"
            )
    
    # Apply modifications
    updates = {}
    if request.guest_name:
        updates["guest_name"] = request.guest_name
    if request.phone:
        updates["phone"] = request.phone
    if request.party_size:
        updates["party_size"] = request.party_size
    if request.start_time:
        updates["start_time"] = request.start_time
    if request.area_pref:
        updates["area_pref"] = request.area_pref
    if request.notes:
        updates["notes"] = request.notes
    
    updated = await service.modify_reservation(reservation.id, **updates)
    
    return ReservationResponse.model_validate(updated)


@router.post("/cancel", response_model=ReservationResponse)
async def cancel_reservation(
    request: ReservationCancel,
    db: AsyncSession = Depends(get_db)
):
    """Cancel a reservation."""
    service = ReservationService(db)
    
    reservation = await service.cancel_reservation(
        reservation_id=request.reservation_id,
        confirmation_code=request.confirmation_code,
        phone=request.phone
    )
    
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    return ReservationResponse.model_validate(reservation)


@router.get("/lookup")
async def lookup_reservation(
    confirmation_code: str = None,
    phone: str = None,
    name: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Look up a reservation by confirmation code, phone, or name."""
    if not any([confirmation_code, phone, name]):
        raise HTTPException(
            status_code=400,
            detail="Provide confirmation_code, phone, or name"
        )
    
    service = ReservationService(db)
    reservation = await service.find_reservation(
        restaurant_id=1,
        confirmation_code=confirmation_code,
        phone=phone,
        guest_name=name
    )
    
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    return ReservationResponse.model_validate(reservation)


@router.get("/upcoming")
async def get_upcoming(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get upcoming reservations."""
    service = ReservationService(db)
    reservations = await service.get_upcoming_reservations(
        restaurant_id=1,
        limit=limit
    )
    
    return [ReservationResponse.model_validate(r) for r in reservations]


# Waitlist endpoints
@router.post("/waitlist/add", response_model=WaitlistResponse)
async def add_to_waitlist(
    request: WaitlistAdd,
    db: AsyncSession = Depends(get_db)
):
    """Add a party to the waitlist."""
    service = WaitlistService(db)
    
    entry, position, wait_time = await service.add_to_waitlist(
        restaurant_id=1,
        guest_name=request.guest_name,
        phone=request.phone,
        party_size=request.party_size,
        notes=request.notes
    )
    
    return WaitlistResponse(
        id=entry.id,
        guest_name=entry.guest_name,
        phone=entry.phone,
        party_size=entry.party_size,
        position=position,
        estimated_wait_min=wait_time,
        status=entry.status
    )


@router.delete("/waitlist/{entry_id}")
async def remove_from_waitlist(
    entry_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Remove entry from waitlist."""
    service = WaitlistService(db)
    entry = await service.remove_from_waitlist(entry_id)
    
    if not entry:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    
    return {"status": "removed", "entry_id": entry_id}


# SMS notification endpoint
@router.post("/notify/sms", response_model=SMSResponse)
async def send_sms_notification(
    request: SMSNotification,
    db: AsyncSession = Depends(get_db)
):
    """Send SMS notification."""
    sms_service = SMSService()
    
    if request.custom_message:
        result = await sms_service.send_custom(request.phone, request.custom_message)
    elif request.reservation_id:
        service = ReservationService(db)
        from sqlalchemy import select
        from app.models import Reservation
        result_query = await db.execute(
            select(Reservation).where(Reservation.id == request.reservation_id)
        )
        reservation = result_query.scalars().first()
        
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservation not found")
        
        if request.message_type == "confirmation":
            result = await sms_service.send_confirmation(reservation)
        elif request.message_type == "reminder":
            result = await sms_service.send_reminder(reservation)
        elif request.message_type == "cancellation":
            result = await sms_service.send_cancellation(reservation)
        else:
            raise HTTPException(status_code=400, detail="Invalid message type")
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide reservation_id or custom_message"
        )
    
    return SMSResponse(**result)
