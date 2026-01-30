"""Menu API endpoints for restaurant menu queries."""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MenuCategory
from app.services.menu_service import MenuService
from app.schemas import (
    MenuItemResponse,
    MenuCategoryInfo,
    MenuAvailabilityCheck,
    MenuAvailabilityResponse
)

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("/{restaurant_id}", response_model=List[MenuItemResponse])
async def get_menu(
    restaurant_id: int,
    category: Optional[MenuCategory] = None,
    available_only: bool = True,
    dietary: Optional[str] = Query(None, description="vegetarian, vegan, or gluten_free"),
    max_price: Optional[float] = None,
    size: Optional[str] = Query(None, description="Small, Medium, Large"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get menu items for a restaurant.

    - **restaurant_id**: Restaurant ID (use 2 for Tony's Pizzeria)
    - **category**: Filter by category (pizza, appetizer, salad, dessert, beverage)
    - **available_only**: Only return available items (default: true)
    - **dietary**: Filter by dietary restriction (vegetarian, vegan, gluten_free)
    - **max_price**: Maximum price filter
    - **size**: Filter by size (Small, Medium, Large)
    """
    service = MenuService(db)
    items = await service.get_menu_items(
        restaurant_id=restaurant_id,
        category=category,
        available_only=available_only,
        dietary=dietary,
        max_price=max_price,
        size=size
    )
    return items


@router.get("/{restaurant_id}/item/{item_id}", response_model=MenuItemResponse)
async def get_menu_item(
    restaurant_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific menu item by ID."""
    service = MenuService(db)
    item = await service.get_item_by_id(restaurant_id, item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    return item


@router.get("/{restaurant_id}/categories", response_model=List[MenuCategoryInfo])
async def get_menu_categories(
    restaurant_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get overview of menu categories with item counts."""
    service = MenuService(db)
    categories = await service.get_categories(restaurant_id)

    return [
        MenuCategoryInfo(
            category=cat["category"],
            item_count=cat["item_count"],
            available_count=cat["available_count"]
        )
        for cat in categories
    ]


@router.get("/{restaurant_id}/search", response_model=List[MenuItemResponse])
async def search_menu(
    restaurant_id: int,
    q: str = Query(..., min_length=1, description="Search query"),
    available_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Search menu items by name or description.

    - **q**: Search query (searches name and description)
    - **available_only**: Only return available items (default: true)
    """
    service = MenuService(db)
    items = await service.search_menu(
        restaurant_id=restaurant_id,
        search_query=q,
        available_only=available_only
    )
    return items


@router.post("/{restaurant_id}/check-availability", response_model=MenuAvailabilityResponse)
async def check_menu_availability(
    restaurant_id: int,
    request: MenuAvailabilityCheck,
    db: AsyncSession = Depends(get_db)
):
    """Check availability of specific menu items."""
    service = MenuService(db)
    availability = await service.check_items_availability(
        restaurant_id=restaurant_id,
        item_ids=request.item_ids
    )
    return MenuAvailabilityResponse(availability=availability)


@router.get("/{restaurant_id}/by-name/{item_name}", response_model=List[MenuItemResponse])
async def get_item_by_name(
    restaurant_id: int,
    item_name: str,
    available_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all variants (sizes) of a menu item by name.

    Useful for getting all size options for a specific pizza.
    """
    service = MenuService(db)
    items = await service.get_items_by_name(
        restaurant_id=restaurant_id,
        name=item_name,
        available_only=available_only
    )

    if not items:
        raise HTTPException(status_code=404, detail=f"No items found with name '{item_name}'")

    return items


@router.get("/{restaurant_id}/facts")
async def get_menu_facts(
    restaurant_id: int,
    category: Optional[MenuCategory] = None,
    dietary: Optional[str] = None,
    max_items: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get menu items formatted as facts for agent context injection.

    This endpoint returns menu information in natural language format
    suitable for injecting into the AI agent's context.

    - **category**: Filter by category
    - **dietary**: Filter by dietary restriction
    - **max_items**: Maximum number of items to include (default: 10)
    """
    service = MenuService(db)

    items = await service.get_menu_items(
        restaurant_id=restaurant_id,
        category=category,
        available_only=True,
        dietary=dietary
    )

    facts = service.format_items_as_facts(items, max_items=max_items)

    # Also get category summary
    categories = await service.get_categories(restaurant_id)
    category_summary = service.format_category_summary(categories)

    return {
        "restaurant_id": restaurant_id,
        "facts": facts,
        "category_summary": category_summary,
        "total_items": len(items),
        "facts_count": len(facts)
    }
