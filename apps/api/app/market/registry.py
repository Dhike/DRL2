import logging
from collections.abc import Callable

from app.config import settings
from app.market.deriv import DerivProvider
from app.market.provider import MarketDataProvider

logger = logging.getLogger("drl2.market.registry")

_FACTORIES: dict[str, Callable[[], MarketDataProvider]] = {
    "deriv": DerivProvider,
}
_providers: dict[str, MarketDataProvider] = {}


def get_provider(name: str | None = None) -> MarketDataProvider:
    key = name or settings.market_provider
    if key not in _FACTORIES:
        raise ValueError(f"Unknown market data provider: {key}")
    if key not in _providers:
        _providers[key] = _FACTORIES[key]()
    return _providers[key]


async def startup_providers(name: str | None = None) -> None:
    """Load the provider's instrument list. A failure is logged, never fatal:
    the first candle request retries the refresh."""
    try:
        provider = get_provider(name)
        count = await provider.refresh_instruments()
        logger.info("Market provider %s ready (%d instruments)", provider.name, count)
    except Exception:
        logger.exception(
            "Market provider startup refresh failed; will retry on first use"
        )


async def shutdown_providers() -> None:
    providers = list(_providers.values())
    _providers.clear()
    for provider in providers:
        await provider.aclose()
