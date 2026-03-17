from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Boolean, Text, ForeignKey, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class TrackedProduct(Base):
    """A product the user is monitoring — their own product."""
    __tablename__ = "tracked_products"

    id          = Column(String, primary_key=True)   # f"{api_key}:{asin}"
    api_key     = Column(String, nullable=False, index=True)
    asin        = Column(String(10), nullable=False)
    title       = Column(Text)
    brand       = Column(String(200))
    image_url   = Column(Text)
    product_url = Column(Text)
    my_price    = Column(Float)
    cost        = Column(Float)
    margin_floor = Column(Float, default=20.0)
    min_viable_price = Column(Float)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("ix_tracked_products_api_key_asin", "api_key", "asin", unique=True),
    )


class Competitor(Base):
    """A competitor product linked to a tracked product."""
    __tablename__ = "competitors"

    id              = Column(String, primary_key=True)  # f"{product_id}:{competitor_asin}"
    product_id      = Column(String, ForeignKey("tracked_products.id"), nullable=False, index=True)
    api_key         = Column(String, nullable=False, index=True)
    asin            = Column(String(10), nullable=False)
    title           = Column(Text)
    brand           = Column(String(200))
    image_url       = Column(Text)
    product_url     = Column(Text)
    discovered_at   = Column(DateTime(timezone=True), server_default=func.now())
    is_active       = Column(Boolean, default=True)


class PriceHistory(Base):
    """Every price snapshot scraped for any ASIN."""
    __tablename__ = "price_history"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    api_key         = Column(String, nullable=False, index=True)
    asin            = Column(String(10), nullable=False, index=True)
    title           = Column(Text)
    current_price   = Column(Float)
    original_price  = Column(Float)
    sale_price      = Column(Float)
    rating          = Column(Float)
    review_count    = Column(Integer)
    availability    = Column(String(100))
    seller          = Column(String(200))
    is_sold_by_amazon = Column(Boolean)
    # Price intelligence fields
    my_price        = Column(Float)
    gap_abs         = Column(Float)
    gap_pct         = Column(Float)
    competitor_cheaper = Column(Boolean)
    urgency         = Column(String(20))
    opportunity_score = Column(Integer)
    recommendation  = Column(String(20))
    margin_at_competitor = Column(Float)
    scraped_at      = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_price_history_api_key_asin", "api_key", "asin"),
        Index("ix_price_history_scraped_at", "scraped_at"),
    )


class AlertLog(Base):
    """Every alert that was fired."""
    __tablename__ = "alert_logs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    api_key         = Column(String, nullable=False, index=True)
    product_asin    = Column(String(10))
    competitor_asin = Column(String(10))
    competitor_title = Column(Text)
    old_price       = Column(Float)
    new_price       = Column(Float)
    gap_pct         = Column(Float)
    urgency         = Column(String(20))
    recommendation  = Column(String(20))
    channel         = Column(String(20))   # discord / telegram / both
    ai_recommendation = Column(Text)
    alert_sent      = Column(Boolean, default=True)
    sent_at         = Column(DateTime(timezone=True), server_default=func.now())
