"""Menu service for querying restaurant menu items."""
from typing import Optional, List
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuItem, MenuCategory


class MenuService:
    """Service for menu operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_menu_items(
        self,
        restaurant_id: int,
        category: Optional[MenuCategory] = None,
        available_only: bool = True,
        dietary: Optional[str] = None,
        max_price: Optional[float] = None,
        size: Optional[str] = None
    ) -> List[MenuItem]:
        """Get menu items with filters."""
        query = select(MenuItem).where(MenuItem.restaurant_id == restaurant_id)

        if category:
            query = query.where(MenuItem.category == category)

        if available_only:
            query = query.where(MenuItem.is_available == True)

        if dietary:
            dietary_lower = dietary.lower()
            if "vegetarian" in dietary_lower:
                query = query.where(MenuItem.is_vegetarian == True)
            elif "vegan" in dietary_lower:
                query = query.where(MenuItem.is_vegan == True)
            elif "gluten" in dietary_lower or "gluten_free" in dietary_lower:
                query = query.where(MenuItem.is_gluten_free == True)

        if max_price:
            query = query.where(MenuItem.price <= max_price)

        if size:
            query = query.where(MenuItem.size == size)

        # Order by category, then by name, then by price
        query = query.order_by(MenuItem.category, MenuItem.name, MenuItem.price)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_menu(
        self,
        restaurant_id: int,
        search_query: str,
        available_only: bool = True
    ) -> List[MenuItem]:
        """Search menu by text query."""
        search_term = f"%{search_query.lower()}%"

        query = select(MenuItem).where(
            MenuItem.restaurant_id == restaurant_id,
            or_(
                func.lower(MenuItem.name).like(search_term),
                func.lower(MenuItem.description).like(search_term)
            )
        )

        if available_only:
            query = query.where(MenuItem.is_available == True)

        query = query.order_by(MenuItem.category, MenuItem.name)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_item_by_id(
        self,
        restaurant_id: int,
        item_id: int
    ) -> Optional[MenuItem]:
        """Get single item by ID."""
        query = select(MenuItem).where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.id == item_id
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_categories(
        self,
        restaurant_id: int
    ) -> List[dict]:
        """Get category overview with counts."""
        # Get all categories with item counts
        query = select(
            MenuItem.category,
            func.count(MenuItem.id).label('total'),
            func.sum(func.cast(MenuItem.is_available, Integer)).label('available')
        ).where(
            MenuItem.restaurant_id == restaurant_id
        ).group_by(MenuItem.category)

        result = await self.db.execute(query)
        rows = result.all()

        categories = []
        for row in rows:
            categories.append({
                "category": row.category,
                "item_count": row.total,
                "available_count": int(row.available) if row.available else 0
            })

        return categories

    async def check_items_availability(
        self,
        restaurant_id: int,
        item_ids: List[int]
    ) -> dict:
        """Check availability of multiple items."""
        query = select(MenuItem.id, MenuItem.is_available).where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.id.in_(item_ids)
        )

        result = await self.db.execute(query)
        rows = result.all()

        availability = {item_id: False for item_id in item_ids}
        for row in rows:
            availability[row.id] = row.is_available

        return availability

    async def get_items_by_name(
        self,
        restaurant_id: int,
        name: str,
        available_only: bool = True
    ) -> List[MenuItem]:
        """Get items by exact name (returns all sizes)."""
        query = select(MenuItem).where(
            MenuItem.restaurant_id == restaurant_id,
            func.lower(MenuItem.name) == name.lower()
        )

        if available_only:
            query = query.where(MenuItem.is_available == True)

        query = query.order_by(MenuItem.price)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    def format_items_as_facts(
        self,
        items: List[MenuItem],
        max_items: int = 10
    ) -> List[str]:
        """Format menu items as fact strings for injection into agent context."""
        if not items:
            return ["No menu items found matching the criteria."]

        facts = []
        items_to_format = items[:max_items]

        # Group items by name (to handle size variants)
        items_by_name = {}
        for item in items_to_format:
            if item.name not in items_by_name:
                items_by_name[item.name] = []
            items_by_name[item.name].append(item)

        for name, variants in items_by_name.items():
            if len(variants) == 1:
                item = variants[0]
                fact = f"{item.name}: {item.description} - ${item.price:.2f}"
                tags = []
                if item.is_vegetarian:
                    tags.append("vegetarian")
                if item.is_vegan:
                    tags.append("vegan")
                if item.is_gluten_free:
                    tags.append("gluten-free")
                if not item.is_available:
                    tags.append("UNAVAILABLE")
                if tags:
                    fact += f" ({', '.join(tags)})"
                facts.append(fact)
            else:
                # Multiple sizes
                item = variants[0]
                prices = []
                for v in sorted(variants, key=lambda x: x.price):
                    size_str = v.size or "Regular"
                    prices.append(f"{size_str}: ${v.price:.2f}")
                fact = f"{name}: {item.description} - {', '.join(prices)}"
                tags = []
                if item.is_vegetarian:
                    tags.append("vegetarian")
                if item.is_vegan:
                    tags.append("vegan")
                if item.is_gluten_free:
                    tags.append("gluten-free")
                if tags:
                    fact += f" ({', '.join(tags)})"
                facts.append(fact)

        if len(items) > max_items:
            facts.append(f"... and {len(items) - max_items} more items")

        return facts

    def format_category_summary(
        self,
        categories: List[dict]
    ) -> str:
        """Format category summary as a single fact string."""
        if not categories:
            return "No menu categories available."

        parts = []
        for cat in categories:
            parts.append(f"{cat['category'].value.title()}: {cat['available_count']} items available")

        return "Menu categories: " + ", ".join(parts)


# Need to import Integer for the cast function
from sqlalchemy import Integer
