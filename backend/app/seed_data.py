"""Seed demo data for the restaurant."""
from datetime import datetime, timedelta
from sqlalchemy import select
from app.database import async_session_maker
from app.models import (
    Restaurant, Table, Reservation, Policy, FAQ, MenuItem,
    TableArea, ReservationStatus, MenuCategory
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

        # ========================================
        # Tony's Pizzeria - Pizza Restaurant
        # ========================================
        pizza_restaurant = Restaurant(
            id=2,
            name="Tony's Pizzeria",
            timezone="America/Los_Angeles",
            phone="(555) 789-0123",
            address="789 Main Street, Downtown CA 92101",
            hours_open="11:00",
            hours_close="23:00"
        )
        db.add(pizza_restaurant)

        # Pizza restaurant tables
        pizza_tables = [
            Table(restaurant_id=2, table_number="T1", capacity=2, area=TableArea.INDOOR, features='{}'),
            Table(restaurant_id=2, table_number="T2", capacity=4, area=TableArea.INDOOR, features='{"booth": true}'),
            Table(restaurant_id=2, table_number="T3", capacity=4, area=TableArea.INDOOR, features='{}'),
            Table(restaurant_id=2, table_number="T4", capacity=6, area=TableArea.INDOOR, features='{"round": true}'),
            Table(restaurant_id=2, table_number="T5", capacity=8, area=TableArea.INDOOR, features='{"large": true}'),
            Table(restaurant_id=2, table_number="P1", capacity=4, area=TableArea.PATIO, features='{"umbrella": true}'),
            Table(restaurant_id=2, table_number="P2", capacity=4, area=TableArea.PATIO, features='{"umbrella": true}'),
            Table(restaurant_id=2, table_number="B1", capacity=2, area=TableArea.BAR, features='{}'),
        ]
        db.add_all(pizza_tables)

        # Pizza restaurant policies
        pizza_policies = [
            Policy(restaurant_id=2, key="dress_code", value="Super casual - come as you are!"),
            Policy(restaurant_id=2, key="cancellation", value="Just give us a call if you can't make it. No fees for cancellations."),
            Policy(restaurant_id=2, key="pets", value="Dogs welcome on the patio! We have water bowls."),
            Policy(restaurant_id=2, key="parking", value="Street parking available. Free lot behind the building."),
            Policy(restaurant_id=2, key="children", value="Very family-friendly! Kids eat free on Tuesdays. High chairs available."),
            Policy(restaurant_id=2, key="delivery", value="Free delivery within 3 miles. $3 fee for 3-5 miles. 30-45 minute estimate."),
            Policy(restaurant_id=2, key="takeout", value="Call ahead orders ready in 15-20 minutes. Curbside pickup available."),
            Policy(restaurant_id=2, key="dietary", value="Gluten-free crust available (+$2). Vegan cheese available (+$2). Please let us know about allergies."),
        ]
        db.add_all(pizza_policies)

        # Pizza restaurant FAQs
        pizza_faqs = [
            FAQ(restaurant_id=2, question="What are your hours?", answer="We're open daily from 11 AM to 11 PM. Late night until midnight on Friday and Saturday!", tags="hours,schedule"),
            FAQ(restaurant_id=2, question="Do you deliver?", answer="Yes! Free delivery within 3 miles, $3 fee for 3-5 miles. Usually 30-45 minutes.", tags="delivery,service"),
            FAQ(restaurant_id=2, question="Do you have gluten-free options?", answer="Yes! We have gluten-free crust available for an extra $2. We also have gluten-free appetizers.", tags="dietary,gluten,allergies"),
            FAQ(restaurant_id=2, question="What's your most popular pizza?", answer="Our Pepperoni Classic is the best seller! The BBQ Chicken is also very popular.", tags="menu,popular,recommendations"),
            FAQ(restaurant_id=2, question="Do you have vegan options?", answer="Absolutely! We have vegan cheese available and our Veggie Deluxe can be made fully vegan.", tags="dietary,vegan"),
            FAQ(restaurant_id=2, question="What sizes do pizzas come in?", answer="All our pizzas come in Small (10 inch), Medium (14 inch), and Large (18 inch).", tags="menu,sizes"),
            FAQ(restaurant_id=2, question="Do you have a kids menu?", answer="Yes! Kids pizza, chicken fingers, and pasta. Kids eat free on Tuesdays!", tags="kids,children,family"),
            FAQ(restaurant_id=2, question="Can I customize my pizza?", answer="Of course! Extra toppings are $1.50-$2.50 each. You can also do half-and-half pizzas.", tags="customization,toppings"),
        ]
        db.add_all(pizza_faqs)

        # ========================================
        # Menu Items for Tony's Pizzeria
        # ========================================
        menu_items = [
            # PIZZAS - Small
            MenuItem(
                restaurant_id=2, name="Margherita", category=MenuCategory.PIZZA,
                description="Fresh mozzarella, San Marzano tomatoes, basil, extra virgin olive oil",
                price=12.99, size="Small", is_available=True, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=15
            ),
            MenuItem(
                restaurant_id=2, name="Margherita", category=MenuCategory.PIZZA,
                description="Fresh mozzarella, San Marzano tomatoes, basil, extra virgin olive oil",
                price=16.99, size="Medium", is_available=True, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=18
            ),
            MenuItem(
                restaurant_id=2, name="Margherita", category=MenuCategory.PIZZA,
                description="Fresh mozzarella, San Marzano tomatoes, basil, extra virgin olive oil",
                price=20.99, size="Large", is_available=True, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=20
            ),
            # Pepperoni
            MenuItem(
                restaurant_id=2, name="Pepperoni Classic", category=MenuCategory.PIZZA,
                description="Loaded with premium pepperoni, mozzarella, house marinara",
                price=13.99, size="Small", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=15
            ),
            MenuItem(
                restaurant_id=2, name="Pepperoni Classic", category=MenuCategory.PIZZA,
                description="Loaded with premium pepperoni, mozzarella, house marinara",
                price=17.99, size="Medium", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=18
            ),
            MenuItem(
                restaurant_id=2, name="Pepperoni Classic", category=MenuCategory.PIZZA,
                description="Loaded with premium pepperoni, mozzarella, house marinara",
                price=21.99, size="Large", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=20
            ),
            # BBQ Chicken
            MenuItem(
                restaurant_id=2, name="BBQ Chicken", category=MenuCategory.PIZZA,
                description="Grilled chicken, red onion, cilantro, BBQ sauce, smoked gouda",
                price=14.99, size="Small", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=18
            ),
            MenuItem(
                restaurant_id=2, name="BBQ Chicken", category=MenuCategory.PIZZA,
                description="Grilled chicken, red onion, cilantro, BBQ sauce, smoked gouda",
                price=18.99, size="Medium", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=20
            ),
            MenuItem(
                restaurant_id=2, name="BBQ Chicken", category=MenuCategory.PIZZA,
                description="Grilled chicken, red onion, cilantro, BBQ sauce, smoked gouda",
                price=22.99, size="Large", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=22
            ),
            # Veggie Deluxe
            MenuItem(
                restaurant_id=2, name="Veggie Deluxe", category=MenuCategory.PIZZA,
                description="Bell peppers, mushrooms, onions, black olives, tomatoes, spinach",
                price=13.99, size="Small", is_available=True, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=15
            ),
            MenuItem(
                restaurant_id=2, name="Veggie Deluxe", category=MenuCategory.PIZZA,
                description="Bell peppers, mushrooms, onions, black olives, tomatoes, spinach",
                price=17.99, size="Medium", is_available=True, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=18
            ),
            MenuItem(
                restaurant_id=2, name="Veggie Deluxe", category=MenuCategory.PIZZA,
                description="Bell peppers, mushrooms, onions, black olives, tomatoes, spinach",
                price=21.99, size="Large", is_available=True, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=20
            ),
            # Meat Lovers
            MenuItem(
                restaurant_id=2, name="Meat Lovers", category=MenuCategory.PIZZA,
                description="Pepperoni, Italian sausage, bacon, ham, ground beef",
                price=15.99, size="Small", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=18
            ),
            MenuItem(
                restaurant_id=2, name="Meat Lovers", category=MenuCategory.PIZZA,
                description="Pepperoni, Italian sausage, bacon, ham, ground beef",
                price=19.99, size="Medium", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=20
            ),
            MenuItem(
                restaurant_id=2, name="Meat Lovers", category=MenuCategory.PIZZA,
                description="Pepperoni, Italian sausage, bacon, ham, ground beef",
                price=24.99, size="Large", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=22
            ),
            # Hawaiian
            MenuItem(
                restaurant_id=2, name="Hawaiian", category=MenuCategory.PIZZA,
                description="Ham, pineapple, mozzarella, house marinara",
                price=13.99, size="Small", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=15
            ),
            MenuItem(
                restaurant_id=2, name="Hawaiian", category=MenuCategory.PIZZA,
                description="Ham, pineapple, mozzarella, house marinara",
                price=17.99, size="Medium", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=18
            ),
            MenuItem(
                restaurant_id=2, name="Hawaiian", category=MenuCategory.PIZZA,
                description="Ham, pineapple, mozzarella, house marinara",
                price=21.99, size="Large", is_available=True, is_vegetarian=False,
                allergens="dairy,gluten", prep_time_min=20
            ),

            # APPETIZERS
            MenuItem(
                restaurant_id=2, name="Garlic Knots", category=MenuCategory.APPETIZER,
                description="Fresh-baked knots brushed with garlic butter, served with marinara",
                price=6.99, size=None, is_available=True, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=10
            ),
            MenuItem(
                restaurant_id=2, name="Mozzarella Sticks", category=MenuCategory.APPETIZER,
                description="Hand-breaded mozzarella, crispy fried, served with marinara",
                price=8.99, size=None, is_available=True, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=10
            ),
            MenuItem(
                restaurant_id=2, name="Buffalo Wings", category=MenuCategory.APPETIZER,
                description="Crispy chicken wings tossed in buffalo sauce, served with ranch",
                price=12.99, size=None, is_available=True, is_vegetarian=False,
                allergens="dairy", prep_time_min=15
            ),
            MenuItem(
                restaurant_id=2, name="Bruschetta", category=MenuCategory.APPETIZER,
                description="Toasted ciabatta topped with fresh tomatoes, basil, garlic, balsamic",
                price=7.99, size=None, is_available=True, is_vegetarian=True, is_vegan=True,
                allergens="gluten", prep_time_min=8
            ),
            MenuItem(
                restaurant_id=2, name="Loaded Potato Skins", category=MenuCategory.APPETIZER,
                description="Crispy potato skins with bacon, cheddar, sour cream, chives",
                price=9.99, size=None, is_available=True, is_vegetarian=False,
                allergens="dairy", prep_time_min=12
            ),

            # SALADS
            MenuItem(
                restaurant_id=2, name="Caesar Salad", category=MenuCategory.SALAD,
                description="Romaine, parmesan, croutons, house Caesar dressing",
                price=9.99, size=None, is_available=True, is_vegetarian=True,
                allergens="dairy,gluten,eggs", prep_time_min=8
            ),
            MenuItem(
                restaurant_id=2, name="Garden Salad", category=MenuCategory.SALAD,
                description="Mixed greens, tomatoes, cucumbers, carrots, choice of dressing",
                price=7.99, size=None, is_available=True, is_vegetarian=True, is_vegan=True, is_gluten_free=True,
                allergens=None, prep_time_min=5
            ),
            MenuItem(
                restaurant_id=2, name="Antipasto Salad", category=MenuCategory.SALAD,
                description="Mixed greens, salami, ham, provolone, olives, pepperoncini, Italian dressing",
                price=12.99, size=None, is_available=True, is_vegetarian=False,
                allergens="dairy", prep_time_min=8
            ),

            # DESSERTS
            MenuItem(
                restaurant_id=2, name="Tiramisu", category=MenuCategory.DESSERT,
                description="Classic Italian dessert with espresso-soaked ladyfingers and mascarpone",
                price=7.99, size=None, is_available=True, is_vegetarian=True,
                allergens="dairy,gluten,eggs", prep_time_min=0
            ),
            MenuItem(
                restaurant_id=2, name="Cannoli", category=MenuCategory.DESSERT,
                description="Crispy pastry shells filled with sweet ricotta and chocolate chips",
                price=5.99, size=None, is_available=True, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=0
            ),
            MenuItem(
                restaurant_id=2, name="Chocolate Lava Cake", category=MenuCategory.DESSERT,
                description="Warm chocolate cake with molten center, served with vanilla ice cream",
                price=8.99, size=None, is_available=True, is_vegetarian=True,
                allergens="dairy,gluten,eggs", prep_time_min=12
            ),
            MenuItem(
                restaurant_id=2, name="Gelato", category=MenuCategory.DESSERT,
                description="Italian ice cream - ask about today's flavors",
                price=4.99, size=None, is_available=True, is_vegetarian=True,
                allergens="dairy", prep_time_min=0
            ),

            # BEVERAGES
            MenuItem(
                restaurant_id=2, name="Soft Drinks", category=MenuCategory.BEVERAGE,
                description="Coke, Diet Coke, Sprite, Fanta, Dr Pepper - free refills",
                price=2.99, size=None, is_available=True, is_vegetarian=True, is_vegan=True, is_gluten_free=True,
                allergens=None, prep_time_min=0
            ),
            MenuItem(
                restaurant_id=2, name="Italian Soda", category=MenuCategory.BEVERAGE,
                description="Sparkling water with your choice of flavored syrup and cream",
                price=3.99, size=None, is_available=True, is_vegetarian=True,
                allergens="dairy", prep_time_min=2
            ),
            MenuItem(
                restaurant_id=2, name="Fresh Lemonade", category=MenuCategory.BEVERAGE,
                description="House-made lemonade, sweetened to perfection",
                price=3.49, size=None, is_available=True, is_vegetarian=True, is_vegan=True, is_gluten_free=True,
                allergens=None, prep_time_min=0
            ),
            MenuItem(
                restaurant_id=2, name="Craft Beer", category=MenuCategory.BEVERAGE,
                description="Rotating selection of local craft beers - ask your server",
                price=6.99, size=None, is_available=True, is_vegetarian=True, is_vegan=True, is_gluten_free=False,
                allergens="gluten", prep_time_min=0
            ),
            MenuItem(
                restaurant_id=2, name="House Wine", category=MenuCategory.BEVERAGE,
                description="Red or white, by the glass",
                price=7.99, size=None, is_available=True, is_vegetarian=True, is_vegan=True, is_gluten_free=True,
                allergens=None, prep_time_min=0
            ),

            # Special item - currently unavailable (for testing)
            MenuItem(
                restaurant_id=2, name="White Truffle Pizza", category=MenuCategory.PIZZA,
                description="Truffle cream sauce, fontina, mushrooms, arugula, shaved parmesan",
                price=24.99, size="Medium", is_available=False, is_vegetarian=True,
                allergens="dairy,gluten", prep_time_min=20
            ),
        ]
        db.add_all(menu_items)

        await db.commit()
