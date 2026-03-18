import os
import hashlib
from typing import List, Optional, Dict
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pydantic import BaseModel

from database import init_db, get_db
from models import TrackedProduct, Competitor, PriceHistory, AlertLog
from schemas import (
    TrackProductRequest,
    PriceSnapshotRequest,
    SuccessResponse,
    PriceHistoryItem,
    CompetitorResponse,
)

load_dotenv()


# ── App lifecycle ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Syphoon Tracking API",
    description="Internal API for storing price intelligence data from the Syphoon n8n node",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth helper ────────────────────────────────────────────────────────────────

def verify_api_key(x_syphoon_key: str = Header(..., alias="X-Syphoon-Key")) -> str:
    if not x_syphoon_key or len(x_syphoon_key) < 8:
        raise HTTPException(status_code=401, detail="Invalid or missing Syphoon API key")
    return x_syphoon_key


# ── Inline schemas for price monitoring ───────────────────────────────────────

class PricesGetRequest(BaseModel):
    asins: List[str]

class PricesSetRequest(BaseModel):
    prices: Dict[str, Optional[float]]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "syphoon-tracking"}


@app.post("/track/product", response_model=SuccessResponse)
async def track_product(
    body: TrackProductRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    product_id = f"{api_key}:{body.product.asin}"

    existing = await db.get(TrackedProduct, product_id)
    if existing:
        existing.title            = body.product.title or existing.title
        existing.brand            = body.product.brand or existing.brand
        existing.image_url        = body.product.image_url or existing.image_url
        existing.my_price         = body.product.my_price or existing.my_price
        existing.cost             = body.product.cost or existing.cost
        existing.margin_floor     = body.product.margin_floor or existing.margin_floor
        existing.min_viable_price = body.product.min_viable_price or existing.min_viable_price
    else:
        db.add(TrackedProduct(
            id               = product_id,
            api_key          = api_key,
            asin             = body.product.asin,
            title            = body.product.title,
            brand            = body.product.brand,
            image_url        = body.product.image_url,
            product_url      = body.product.product_url,
            my_price         = body.product.my_price,
            cost             = body.product.cost,
            margin_floor     = body.product.margin_floor,
            min_viable_price = body.product.min_viable_price,
        ))

    for comp in (body.competitors or []):
        comp_id = f"{product_id}:{comp.asin}"
        existing_comp = await db.get(Competitor, comp_id)
        if not existing_comp:
            db.add(Competitor(
                id          = comp_id,
                product_id  = product_id,
                api_key     = api_key,
                asin        = comp.asin,
                title       = comp.title,
                brand       = comp.brand,
                image_url   = comp.image_url,
                product_url = comp.product_url,
            ))

    await db.commit()
    return SuccessResponse(message=f"Product {body.product.asin} tracked with {len(body.competitors or [])} competitors")


@app.post("/track/price", response_model=SuccessResponse)
async def track_price(
    body: PriceSnapshotRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    snapshot = PriceHistory(
        api_key            = api_key,
        asin               = body.asin,
        title              = body.title,
        current_price      = body.current_price,
        original_price     = body.original_price,
        sale_price         = body.sale_price,
        rating             = body.rating,
        review_count       = body.review_count,
        availability       = body.availability,
        seller             = body.seller,
        is_sold_by_amazon  = body.is_sold_by_amazon,
        my_price           = body.my_price,
        gap_abs            = body.gap_abs,
        gap_pct            = body.gap_pct,
        competitor_cheaper = body.competitor_cheaper,
        urgency            = body.urgency,
        opportunity_score  = body.opportunity_score,
        recommendation     = body.recommendation,
        margin_at_competitor = body.margin_at_competitor,
    )
    db.add(snapshot)

    if body.alert_sent and body.alert_channel:
        db.add(AlertLog(
            api_key           = api_key,
            product_asin      = body.product_asin,
            competitor_asin   = body.asin,
            competitor_title  = body.title,
            new_price         = body.current_price,
            gap_pct           = body.gap_pct,
            urgency           = body.urgency,
            recommendation    = body.recommendation,
            channel           = body.alert_channel,
            ai_recommendation = body.ai_recommendation,
            alert_sent        = body.alert_sent,
        ))

    await db.commit()
    return SuccessResponse(message=f"Price snapshot saved for {body.asin}")


@app.post("/prices/get")
async def get_prices(
    body: PricesGetRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the Syphoon n8n node before monitoring a batch of competitors.
    Returns the last known price for each ASIN, or null if never seen before.
    """
    if not body.asins:
        return {"prices": {}}

    result = await db.execute(
        select(PriceHistory.asin, PriceHistory.current_price, PriceHistory.scraped_at)
        .where(
            PriceHistory.api_key == api_key,
            PriceHistory.asin.in_(body.asins),
        )
        .order_by(desc(PriceHistory.scraped_at))
    )
    rows = result.all()

    # Keep only the most recent price per ASIN
    latest: Dict[str, Optional[float]] = {}
    for row in rows:
        if row.asin not in latest:
            latest[row.asin] = float(row.current_price) if row.current_price is not None else None

    # Fill null for any ASINs not yet in DB
    prices = {asin: latest.get(asin, None) for asin in body.asins}
    return {"prices": prices}


@app.post("/prices/set")
async def set_prices(
    body: PricesSetRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the Syphoon n8n node after monitoring a batch of competitors.
    Saves a lightweight price snapshot for each ASIN so the next run can compare.
    Uses the existing PriceHistory model — no new table needed.
    """
    if not body.prices:
        return {"ok": True, "stored": 0}

    count = 0
    for asin, price in body.prices.items():
        if price is None:
            continue
        db.add(PriceHistory(
            api_key       = api_key,
            asin          = asin,
            current_price = price,
        ))
        count += 1

    await db.commit()
    return {"ok": True, "stored": count}


# ── Read endpoints ─────────────────────────────────────────────────────────────

@app.get("/data/products")
async def get_products(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TrackedProduct).where(TrackedProduct.api_key == api_key)
    )
    products = result.scalars().all()
    return {"products": [
        {
            "asin":         p.asin,
            "title":        p.title,
            "my_price":     p.my_price,
            "cost":         p.cost,
            "margin_floor": p.margin_floor,
            "created_at":   p.created_at,
        }
        for p in products
    ]}


@app.get("/data/competitors/{product_asin}")
async def get_competitors(
    product_asin: str,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    product_id = f"{api_key}:{product_asin}"
    result = await db.execute(
        select(Competitor).where(
            Competitor.product_id == product_id,
            Competitor.is_active == True,
        )
    )
    competitors = result.scalars().all()
    return {"competitors": [
        {
            "asin":          c.asin,
            "title":         c.title,
            "image_url":     c.image_url,
            "product_url":   c.product_url,
            "discovered_at": c.discovered_at,
        }
        for c in competitors
    ]}


@app.get("/data/history/{asin}")
async def get_price_history(
    asin: str,
    limit: int = 100,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.api_key == api_key, PriceHistory.asin == asin)
        .order_by(desc(PriceHistory.scraped_at))
        .limit(limit)
    )
    rows = result.scalars().all()
    return {"asin": asin, "history": [
        {
            "price":          r.current_price,
            "urgency":        r.urgency,
            "recommendation": r.recommendation,
            "gap_pct":        r.gap_pct,
            "scraped_at":     r.scraped_at,
        }
        for r in rows
    ]}


@app.get("/data/alerts")
async def get_alerts(
    limit: int = 50,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlertLog)
        .where(AlertLog.api_key == api_key)
        .order_by(desc(AlertLog.sent_at))
        .limit(limit)
    )
    alerts = result.scalars().all()
    return {"alerts": [
        {
            "competitor_asin":   a.competitor_asin,
            "competitor_title":  a.competitor_title,
            "new_price":         a.new_price,
            "gap_pct":           a.gap_pct,
            "urgency":           a.urgency,
            "recommendation":    a.recommendation,
            "channel":           a.channel,
            "ai_recommendation": a.ai_recommendation,
            "sent_at":           a.sent_at,
        }
        for a in alerts
    ]}
