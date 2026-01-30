"""SQLAlchemy models for restaurant reservation system."""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class WaitlistStatus(str, enum.Enum):
    WAITING = "waiting"
    SEATED = "seated"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TableArea(str, enum.Enum):
    INDOOR = "indoor"
    PATIO = "patio"
    BAR = "bar"
    PRIVATE = "private"


class MenuCategory(str, enum.Enum):
    """Menu item categories."""
    PIZZA = "pizza"
    APPETIZER = "appetizer"
    SALAD = "salad"
    DESSERT = "dessert"
    BEVERAGE = "beverage"


class Restaurant(Base):
    """Restaurant information."""
    __tablename__ = "restaurants"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="America/New_York")
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    hours_open: Mapped[str] = mapped_column(String(10), default="11:00")
    hours_close: Mapped[str] = mapped_column(String(10), default="22:00")
    
    # Relationships
    tables: Mapped[list["Table"]] = relationship(back_populates="restaurant")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="restaurant")
    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(back_populates="restaurant")
    policies: Mapped[list["Policy"]] = relationship(back_populates="restaurant")
    faqs: Mapped[list["FAQ"]] = relationship(back_populates="restaurant")
    menu_items: Mapped[list["MenuItem"]] = relationship(back_populates="restaurant")


class Table(Base):
    """Restaurant table inventory."""
    __tablename__ = "tables"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    table_number: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    area: Mapped[TableArea] = mapped_column(SQLEnum(TableArea), default=TableArea.INDOOR)
    features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: wheelchair, window, booth
    
    restaurant: Mapped["Restaurant"] = relationship(back_populates="tables")


class Reservation(Base):
    """Reservation records."""
    __tablename__ = "reservations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, default=90)
    area_pref: Mapped[Optional[TableArea]] = mapped_column(SQLEnum(TableArea), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ReservationStatus] = mapped_column(
        SQLEnum(ReservationStatus), 
        default=ReservationStatus.CONFIRMED
    )
    confirmation_code: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    restaurant: Mapped["Restaurant"] = relationship(back_populates="reservations")


class WaitlistEntry(Base):
    """Waitlist records."""
    __tablename__ = "waitlist"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[WaitlistStatus] = mapped_column(
        SQLEnum(WaitlistStatus),
        default=WaitlistStatus.WAITING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    restaurant: Mapped["Restaurant"] = relationship(back_populates="waitlist_entries")


class Policy(Base):
    """Restaurant policies."""
    __tablename__ = "policies"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    
    restaurant: Mapped["Restaurant"] = relationship(back_populates="policies")


class FAQ(Base):
    """Frequently asked questions."""
    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # comma-separated

    restaurant: Mapped["Restaurant"] = relationship(back_populates="faqs")


class MenuItem(Base):
    """Menu items for restaurants."""
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[MenuCategory] = mapped_column(SQLEnum(MenuCategory), nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)
    size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Small, Medium, Large
    is_available: Mapped[bool] = mapped_column(default=True)
    is_vegetarian: Mapped[bool] = mapped_column(default=False)
    is_vegan: Mapped[bool] = mapped_column(default=False)
    is_gluten_free: Mapped[bool] = mapped_column(default=False)
    allergens: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # comma-separated
    prep_time_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    restaurant: Mapped["Restaurant"] = relationship(back_populates="menu_items")
