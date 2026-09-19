import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import get_current_user
from app.market.models import Timeframe
from app.market.provider import MarketDataError
from app.market.schemas import CandleOut, CandlesOut, InstrumentOut, InstrumentsOut
from app.market.service import (
    MarketService,
    UnknownInstrumentError,
    get_market_service,
)
from app.models import User

logger = logging.getLogger("drl2.market")

router = APIRouter(prefix="/market", tags=["market"])


async def get_service() -> MarketService:
    return get_market_service()


@router.get("/instruments", response_model=InstrumentsOut)
async def list_instruments(
    _: User = Depends(get_current_user),
    service: MarketService = Depends(get_service),
) -> InstrumentsOut:
    return InstrumentsOut(
        provider=service.provider_name,
        instruments=[
            InstrumentOut(symbol=i.symbol, market=i.market.value)
            for i in service.instruments()
        ],
        timeframes=[tf.value for tf in service.timeframes()],
    )


@router.get("/candles", response_model=CandlesOut)
async def get_candles(
    symbol: str = Query(min_length=1, max_length=32),
    timeframe: Timeframe = Query(),
    limit: int = Query(200, ge=1, le=1000),
    closed_only: bool = Query(False),
    _: User = Depends(get_current_user),
    service: MarketService = Depends(get_service),
) -> CandlesOut:
    try:
        candles = await service.get_candles(symbol, timeframe, limit, closed_only)
    except UnknownInstrumentError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown instrument")
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except MarketDataError:
        logger.exception("Market data request failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Market data is temporarily unavailable"
        )
    return CandlesOut(
        provider=service.provider_name,
        symbol=symbol,
        timeframe=timeframe.value,
        candles=[CandleOut.from_candle(candle) for candle in candles],
    )
