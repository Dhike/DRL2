from collections.abc import Callable

from app.config import settings
from app.market.gate import GateProvider
from app.market.provider import MarketDataProvider

_FACTORIES: dict[str, Callable[[], MarketDataProvider]] = {"gate": GateProvider}
_providers: dict[str, MarketDataProvider] = {}


def get_provider(name: str | None = None) -> MarketDataProvider:
    key = name or settings.market_provider
    if key not in _FACTORIES:
        raise ValueError(f"Unknown market data provider: {key}")
    if key not in _providers:
        _providers[key] = _FACTORIES[key]()
    return _providers[key]


async def shutdown_providers() -> None:
    providers = list(_providers.values())
    _providers.clear()
    for provider in providers:
        await provider.aclose()
