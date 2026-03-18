from pydantic import BaseModel
from typing import Dict, Optional

# ── Add these two schemas (put near your other schemas or inline here) ─────────

class PricesGetRequest(BaseModel):
    asins: List[str]

class PricesSetRequest(BaseModel):
    prices: Dict[str, Optional[float]]


# ── Add these two endpoints to your existing main.py ──────────────────────────
# Place them anywhere after your existing endpoints, e.g. after /track/price

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

    # Fill in null for any ASINs not yet in DB
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
    Uses your existing PriceHistory model — no new table needed.
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
            # all other fields left as None — this is a monitor snapshot, not a full scrape
        ))
        count += 1

    await db.commit()
    return {"ok": True, "stored": count}
