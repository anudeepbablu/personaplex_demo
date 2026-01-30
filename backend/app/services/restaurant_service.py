"""Service for loading restaurant data as facts for AI context."""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Restaurant, Policy, FAQ, MenuItem, MenuCategory


class RestaurantService:
    """Service to load restaurant information from database."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_restaurant(self, restaurant_id: int) -> Optional[Restaurant]:
        """Get restaurant by ID."""
        result = await self.db.execute(
            select(Restaurant).where(Restaurant.id == restaurant_id)
        )
        return result.scalars().first()

    async def get_restaurant_config(self, restaurant_id: int) -> dict:
        """Get restaurant configuration for system prompt."""
        restaurant = await self.get_restaurant(restaurant_id)
        if not restaurant:
            return {}

        # Get policies
        policies_result = await self.db.execute(
            select(Policy).where(Policy.restaurant_id == restaurant_id)
        )
        policies = {p.key: p.value for p in policies_result.scalars().all()}

        return {
            "name": restaurant.name,
            "address": restaurant.address or "Address not available",
            "phone": restaurant.phone or "Phone not available",
            "hours": f"{restaurant.hours_open} - {restaurant.hours_close}",
            "policies": policies
        }

    async def get_policies_as_facts(self, restaurant_id: int) -> List[str]:
        """Get restaurant policies formatted as facts."""
        result = await self.db.execute(
            select(Policy).where(Policy.restaurant_id == restaurant_id)
        )
        policies = result.scalars().all()

        facts = []
        for policy in policies:
            key_formatted = policy.key.replace('_', ' ').title()
            facts.append(f"{key_formatted}: {policy.value}")

        return facts

    async def get_faqs_as_facts(self, restaurant_id: int) -> List[str]:
        """Get FAQs formatted as facts."""
        result = await self.db.execute(
            select(FAQ).where(FAQ.restaurant_id == restaurant_id)
        )
        faqs = result.scalars().all()

        facts = []
        for faq in faqs:
            facts.append(f"Q: {faq.question} A: {faq.answer}")

        return facts

    async def get_menu_as_facts(self, restaurant_id: int) -> List[str]:
        """Get menu items formatted as facts for AI context."""
        result = await self.db.execute(
            select(MenuItem)
            .where(MenuItem.restaurant_id == restaurant_id)
            .order_by(MenuItem.category, MenuItem.name, MenuItem.price)
        )
        items = result.scalars().all()

        if not items:
            return ["No menu items available."]

        # Group items by name (to handle size variants)
        items_by_name = {}
        for item in items:
            key = (item.category.value, item.name)
            if key not in items_by_name:
                items_by_name[key] = []
            items_by_name[key].append(item)

        facts = []

        # Add category headers and items
        current_category = None
        for (category, name), variants in items_by_name.items():
            # Add category header
            if category != current_category:
                current_category = category
                facts.append(f"--- {category.upper()} MENU ---")

            # Format item with all size variants
            item = variants[0]  # Use first for description
            if len(variants) == 1:
                # Single size/price
                availability = "" if item.is_available else " [UNAVAILABLE]"
                dietary = []
                if item.is_vegetarian:
                    dietary.append("V")
                if item.is_vegan:
                    dietary.append("VG")
                if item.is_gluten_free:
                    dietary.append("GF")
                dietary_str = f" ({', '.join(dietary)})" if dietary else ""

                facts.append(
                    f"{item.name}: {item.description} - ${item.price:.2f}{dietary_str}{availability}"
                )
            else:
                # Multiple sizes
                prices = []
                for v in sorted(variants, key=lambda x: x.price):
                    size_str = v.size or "Regular"
                    avail = "" if v.is_available else " [N/A]"
                    prices.append(f"{size_str} ${v.price:.2f}{avail}")

                dietary = []
                if item.is_vegetarian:
                    dietary.append("vegetarian")
                if item.is_vegan:
                    dietary.append("vegan")
                if item.is_gluten_free:
                    dietary.append("gluten-free")
                dietary_str = f" - {', '.join(dietary)}" if dietary else ""

                facts.append(
                    f"{item.name}: {item.description} - {', '.join(prices)}{dietary_str}"
                )

        return facts

    async def get_menu_summary(self, restaurant_id: int) -> str:
        """Get a brief menu summary."""
        result = await self.db.execute(
            select(MenuItem.category, MenuItem.is_available)
            .where(MenuItem.restaurant_id == restaurant_id)
        )
        rows = result.all()

        if not rows:
            return "Menu not available."

        # Count by category
        categories = {}
        for category, is_available in rows:
            cat_name = category.value
            if cat_name not in categories:
                categories[cat_name] = {"total": 0, "available": 0}
            categories[cat_name]["total"] += 1
            if is_available:
                categories[cat_name]["available"] += 1

        parts = []
        for cat, counts in categories.items():
            parts.append(f"{counts['available']} {cat}s")

        return f"Menu includes: {', '.join(parts)}"

    async def load_all_facts(self, restaurant_id: int) -> List[str]:
        """Load all restaurant facts from database for AI context."""
        facts = []

        # Get restaurant info
        restaurant = await self.get_restaurant(restaurant_id)
        if restaurant:
            facts.append(f"Restaurant: {restaurant.name}")
            facts.append(f"Location: {restaurant.address}")
            facts.append(f"Phone: {restaurant.phone}")
            facts.append(f"Hours: {restaurant.hours_open} to {restaurant.hours_close}")

        # Get policies
        policy_facts = await self.get_policies_as_facts(restaurant_id)
        if policy_facts:
            facts.append("--- POLICIES ---")
            facts.extend(policy_facts)

        # Get menu
        menu_facts = await self.get_menu_as_facts(restaurant_id)
        if menu_facts:
            facts.extend(menu_facts)

        # Get FAQs (limit to avoid context overflow)
        faq_facts = await self.get_faqs_as_facts(restaurant_id)
        if faq_facts:
            facts.append("--- FREQUENTLY ASKED QUESTIONS ---")
            facts.extend(faq_facts[:10])  # Limit FAQs

        return facts
