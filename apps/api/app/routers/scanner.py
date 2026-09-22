import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_current_user
from app.market.provider import MarketDataError
from app.market.service import (
    MarketService,
    UnknownInstrumentError,
    get_market_service,
)
from app.models import User
from app.scanner.models import ScannerRequest, ScannerStatus
from app.scanner.schemas import ScannerScanRequest, ScannerScanResult, ScannerSignalOut
from app.scanner.strategies import run_strategies

logger = logging.getLogger("drl2.scanner")

router = APIRouter(prefix="/scanner", tags=["scanner"])


async def get_service() -> MarketService:
    return get_market_service()


@router.post("/scan", response_model=ScannerScanResult)
async def scan(
    request: ScannerScanRequest,
    _: User = Depends(get_current_user),
    service: MarketService = Depends(get_service),
) -> ScannerScanResult:
    try:
        instrument = service.find_instrument(request.symbol)
    except UnknownInstrumentError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown instrument")

    try:
        candles = await service.get_candles(request.symbol, request.timeframe)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    except MarketDataError:
        logger.exception("Market data request failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Market data is temporarily unavailable"
        )

    scanner_request = ScannerRequest(
        market=instrument.market.value,
        symbol=request.symbol,
        timeframe=request.timeframe.value,
        strategies=tuple(request.strategies),
    )

    try:
        signals = run_strategies(scanner_request, candles, scope=request.scope)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))

    return ScannerScanResult(
        status=ScannerStatus.COMPLETED,
        signals=[ScannerSignalOut.from_signal(s) for s in signals],
    )
