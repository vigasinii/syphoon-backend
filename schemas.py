from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── Inbound from n8n node ──────────────────────────────────────────────────────

class ProductData(BaseModel):
    asin: str
    title: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    my_price: Optional[float] = None
    cost: Optional[float] = None
    margin_floor: Optional[float] = 20.0
    min_viable_price: Optional[float] = None


class CompetitorData(BaseModel):
    asin: str
    title: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None


class TrackProductRequest(BaseModel):
    """Posted by node after discoverCompetitors or first getProductIntelligence."""
    product: ProductData
    competitors: Optional[List[CompetitorData]] = []


class PriceSnapshotRequest(BaseModel):
    """Posted by node after every scrape operation."""
    asin: str
    title: Optional[str] = None
    current_price: Optional[float] = None
    original_price: Optional[float] = None
    sale_price: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    availability: Optional[str] = None
    seller: Optional[str] = None
    is_sold_by_amazon: Optional[bool] = None
    # Price intelligence
    my_price: Optional[float] = None
    gap_abs: Optional[float] = None
    gap_pct: Optional[float] = None
    competitor_cheaper: Optional[bool] = None
    urgency: Optional[str] = None
    opportunity_score: Optional[int] = None
    recommendation: Optional[str] = None
    margin_at_competitor: Optional[float] = None
    # Alert info
    alert_sent: Optional[bool] = False
    alert_channel: Optional[str] = None
    ai_recommendation: Optional[str] = None
    # For alert log
    product_asin: Optional[str] = None  # the user's own product ASIN


# ── Outbound responses ─────────────────────────────────────────────────────────

class SuccessResponse(BaseModel):
    success: bool = True
    message: str


class PriceHistoryItem(BaseModel):
    asin: str
    current_price: Optional[float]
    urgency: Optional[str]
    recommendation: Optional[str]
    scraped_at: datetime

    class Config:
        from_attributes = True


class CompetitorResponse(BaseModel):
    asin: str
    title: Optional[str]
    image_url: Optional[str]
    product_url: Optional[str]

    class Config:
        from_attributes = True
