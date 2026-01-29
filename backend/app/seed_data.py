"""Seed demo data for the restaurant."""
from datetime import datetime, timedelta
from sqlalchemy import select
from app.database import async_session_maker
from app.models import (
    Restaurant, Table, Reservation, Policy, FAQ,
    TableArea, ReservationStatus
)


async def seed_demo_data():
    """Seed the database with demo restaurant data."""
    async with async_session_maker() as db:
        # Check if already seeded
        result = await db.execute(select(Restaurant))
        if result.scalars().first():
            return  # Already seeded
        
        # Create restaurant
        restaurant = Restaurant(
            id=1,
            name="The Riverside Grill",
            timezone="America/Los_Angeles",
            phone="(555) 234-5678",
            address="456 Harbor View Drive, Lakeside CA 92040",
            hours_open="11:00",
            hours_close="22:00"
        )
        db.add(restaurant)
        
        # Create tables
        tables = [
            # Indoor tables
            Table(restaurant_id=1, table_number="I1", capacity=2, area=TableArea.INDOOR, features='{"window": true}'),
            Table(restaurant_id=1, table_number="I2", capacity=2, area=TableArea.INDOOR, features='{"booth": true}'),
            Table(restaurant_id=1, table_number="I3", capacity=4, area=TableArea.INDOOR, features='{"window": true}'),
            Table(restaurant_id=1, table_number="I4", capacity=4, area=TableArea.INDOOR, features='{"booth": true}'),
            Table(restaurant_id=1, table_number="I5", capacity=6, area=TableArea.INDOOR, features='{}'),
            Table(restaurant_id=1, table_number="I6", capacity=8, area=TableArea.INDOOR, features='{"round": true}'),
            # Patio tables
            Table(restaurant_id=1, table_number="P1", capacity=2, area=TableArea.PATIO, features='{"umbrella": true}'),
            Table(restaurant_id=1, table_number="P2", capacity=4, area=TableArea.PATIO, features='{"umbrella": true}'),
            Table(restaurant_id=1, table_number="P3", capacity=4, area=TableArea.PATIO, features='{"heater": true}'),
            Table(restaurant_id=1, table_number="P4", capacity=6, area=TableArea.PATIO, features='{"fire_pit": true}'),
            # Bar seating
            Table(restaurant_id=1, table_number="B1", capacity=2, area=TableArea.BAR, features='{}'),
            Table(restaurant_id=1, table_number="B2", capacity=2, area=TableArea.BAR, features='{}'),
            Table(restaurant_id=1, table_number="B3", capacity=4, area=TableArea.BAR, features='{"high_top": true}'),
            # Private dining
            Table(restaurant_id=1, table_number="PR1", capacity=12, area=TableArea.PRIVATE, features='{"av_equipment": true}'),
        ]
        db.add_all(tables)
        
        # Create policies
        policies = [
            Policy(restaurant_id=1, key="dress_code", value="Smart casual attire requested. No athletic wear, please."),
            Policy(restaurant_id=1, key="cancellation", value="24 hours notice appreciated. Same-day cancellations may incur a $20 per person fee."),
            Policy(restaurant_id=1, key="pets", value="Service animals welcome inside. Well-behaved dogs permitted on our patio."),
            Policy(restaurant_id=1, key="parking", value="Free parking lot behind the building. Complimentary valet Friday-Sunday evenings."),
            Policy(restaurant_id=1, key="children", value="Family-friendly! Kids menu, high chairs, and booster seats available."),
            Policy(restaurant_id=1, key="large_parties", value="Groups of 8+ require a credit card to hold the reservation."),
            Policy(restaurant_id=1, key="private_dining", value="Private dining room available for events up to 12 guests. $500 minimum spend."),
            Policy(restaurant_id=1, key="dietary", value="We accommodate most dietary restrictions. Please inform us of allergies. We cannot guarantee allergen-free preparation in a shared kitchen."),
        ]
        db.add_all(policies)
        
        # Create FAQs
        faqs = [
            FAQ(restaurant_id=1, question="What are your hours?", answer="We're open Tuesday through Sunday, 11 AM to 10 PM. We're closed on Mondays.", tags="hours,schedule"),
            FAQ(restaurant_id=1, question="Where can I park?", answer="We have a free parking lot behind the building. Valet is available Friday through Sunday evenings.", tags="parking,location"),
            FAQ(restaurant_id=1, question="Do you have gluten-free options?", answer="Yes! We have a dedicated gluten-free section on our menu. Please inform your server of any allergies.", tags="dietary,gluten,allergies"),
            FAQ(restaurant_id=1, question="Do you have vegetarian/vegan options?", answer="Absolutely! We have several vegetarian and vegan dishes. Items are marked on the menu with V and VG symbols.", tags="dietary,vegetarian,vegan"),
            FAQ(restaurant_id=1, question="Do you allow pets?", answer="Service animals are welcome inside. Well-behaved dogs are welcome on our patio.", tags="pets,dogs"),
            FAQ(restaurant_id=1, question="Is there a dress code?", answer="We ask for smart casual attire. No athletic wear, please.", tags="dress,attire"),
            FAQ(restaurant_id=1, question="Do you have a kids menu?", answer="Yes! We have a great kids menu with smaller portions. High chairs and booster seats are available.", tags="kids,children,family"),
            FAQ(restaurant_id=1, question="Do you have outdoor seating?", answer="Yes, we have a beautiful patio with heaters and umbrellas. It's first-come or can be requested for reservations.", tags="patio,outdoor,seating"),
            FAQ(restaurant_id=1, question="Can you accommodate large groups?", answer="Absolutely! We can seat groups up to 12 in our private dining room. For 8+ guests, we do require a credit card to hold the reservation.", tags="groups,parties,private"),
            FAQ(restaurant_id=1, question="What's your cancellation policy?", answer="We appreciate 24 hours notice for cancellations. Same-day cancellations may incur a $20 per person fee.", tags="cancellation,policy"),
            FAQ(restaurant_id=1, question="Do you have a happy hour?", answer="Yes! Happy hour is Tuesday through Friday, 4 PM to 6 PM. Half-price appetizers and $2 off drinks.", tags="happy hour,drinks,specials"),
            FAQ(restaurant_id=1, question="Do you take walk-ins?", answer="We do accept walk-ins based on availability. For guaranteed seating, we recommend making a reservation.", tags="walk-in,availability"),
        ]
        db.add_all(faqs)
        
        # Create some sample reservations (for demo)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        sample_reservations = [
            Reservation(
                restaurant_id=1,
                guest_name="John Smith",
                phone="5551234567",
                party_size=4,
                start_time=today.replace(hour=18, minute=30),
                area_pref=TableArea.INDOOR,
                notes="Anniversary dinner",
                status=ReservationStatus.CONFIRMED,
                confirmation_code="ABC123"
            ),
            Reservation(
                restaurant_id=1,
                guest_name="Sarah Johnson",
                phone="5559876543",
                party_size=2,
                start_time=today.replace(hour=19, minute=0),
                area_pref=TableArea.PATIO,
                notes=None,
                status=ReservationStatus.CONFIRMED,
                confirmation_code="DEF456"
            ),
            Reservation(
                restaurant_id=1,
                guest_name="Mike Williams",
                phone="5555551234",
                party_size=6,
                start_time=today.replace(hour=19, minute=0),
                area_pref=TableArea.INDOOR,
                notes="Birthday celebration - need cake served at 8pm",
                status=ReservationStatus.CONFIRMED,
                confirmation_code="GHI789"
            ),
            Reservation(
                restaurant_id=1,
                guest_name="Demo Fully Booked",
                phone="5550000001",
                party_size=4,
                start_time=today.replace(hour=19, minute=0),
                area_pref=TableArea.INDOOR,
                status=ReservationStatus.CONFIRMED,
                confirmation_code="FULL01"
            ),
            Reservation(
                restaurant_id=1,
                guest_name="Demo Fully Booked 2",
                phone="5550000002",
                party_size=4,
                start_time=today.replace(hour=19, minute=0),
                area_pref=TableArea.INDOOR,
                status=ReservationStatus.CONFIRMED,
                confirmation_code="FULL02"
            ),
        ]
        db.add_all(sample_reservations)
        
        await db.commit()
