"""Chart generation helpers for statistics views."""

from __future__ import annotations

import json
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from cycler import cycler
from matplotlib.ticker import MaxNLocator

from core.redis_client import redis_client
from core.telemetry import logger
from services.stats.schemas import StatsWindow, StatsWindowMode
from services.stats.service import StatsService

_DARK_BG = "#212946"
_GRID_COLOR = "#2A3459"
_PRIMARY_COLOR = "#18c0c4"
_BAR_COLOR = "#2a3459"
_TEXT_COLOR = "0.9"
_CACHE_PREFIX = "stats:chart"
_CACHE_TTL_SECONDS = 60 * 60 * 30  # ~30 horas


@dataclass(frozen=True)
class ChartResult:
    """Container for chart metadata returned to handlers."""

    path: Path
    fresh: bool


# Style configuration (inspired by Seaborn + mplcyberpunk)
plt.rcParams.update(
    {
        "legend.frameon": False,
        "legend.numpoints": 1,
        "legend.scatterpoints": 1,
        "axes.axisbelow": True,
        "font.family": "sans-serif",
        "font.sans-serif": [
            "Overpass",
            "Helvetica",
            "Helvetica Neue",
            "Arial",
            "Liberation Sans",
            "DejaVu Sans",
            "Bitstream Vera Sans",
            "sans-serif",
        ],
        "axes.grid": True,
        "axes.edgecolor": "white",
        "axes.linewidth": 0,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "xtick.minor.size": 0,
        "ytick.minor.size": 0,
        "grid.linestyle": "-",
        "grid.color": _GRID_COLOR,
        "lines.solid_capstyle": "round",
        "text.color": _TEXT_COLOR,
        "axes.labelcolor": _TEXT_COLOR,
        "xtick.color": _TEXT_COLOR,
        "ytick.color": _TEXT_COLOR,
        "axes.prop_cycle": cycler(
            "color",
            [
                "#18c0c4",
                "#f62196",
                "#A267F5",
                "#f3907e",
                "#ffe46b",
                "#fefeff",
            ],
        ),
        "image.cmap": "RdPu",
        "figure.facecolor": _DARK_BG,
        "axes.facecolor": _DARK_BG,
        "savefig.facecolor": _DARK_BG,
    }
)


def _series_for_window(
    service: StatsService, window: StatsWindow, days: int
) -> List[Tuple[date, int]]:
    target_day = (
        window.end_date
        if window.mode == StatsWindowMode.RANGE
        else window.day or date.today()
    )
    return service.daily_sales_series(days=days, end_date=target_day)


def generate_sales_chart(
    service: StatsService,
    window: StatsWindow,
    *,
    days: int = 7,
    force: bool = False,
) -> Optional[ChartResult]:
    key = _cache_key(service.owner_id, window, days)

    cached_path = None
    if not force:
        try:
            cached_path = _load_cached_chart(key)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Failed to load cached chart",
                extra={"owner_id": service.owner_id, "error": str(exc)},
            )

        if cached_path:
            return ChartResult(path=cached_path, fresh=False)
    else:
        # Força atualização, mas guarda gráfico antigo para limpeza
        try:
            cached_path = _load_cached_chart(key)
        except Exception:  # noqa: BLE001
            cached_path = None

    chart_path = _build_chart(service, window, days)
    if not chart_path:
        redis_client.delete(key)
        if cached_path:
            _safe_remove(cached_path)
        return None

    _store_chart(key, chart_path)
    if cached_path and cached_path != chart_path:
        _safe_remove(cached_path)
    return ChartResult(path=chart_path, fresh=True)


def _cache_key(owner_id: int, window: StatsWindow, days: int) -> str:
    start_iso = window.start_date.isoformat()
    end_iso = window.end_date.isoformat()
    return (
        f"{_CACHE_PREFIX}:{owner_id}:{window.mode.value}:{start_iso}:{end_iso}:{days}"
    )


def _load_cached_chart(key: str) -> Optional[Path]:
    raw = redis_client.get(key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        redis_client.delete(key)
        return None

    path_value = data.get("path")
    if not path_value:
        redis_client.delete(key)
        return None

    path = Path(path_value)
    if not path.is_file():
        redis_client.delete(key)
        return None
    return path


def _store_chart(key: str, path: Path) -> None:
    payload = json.dumps({"path": str(path), "generated_at": int(time.time())})
    redis_client.setex(key, _CACHE_TTL_SECONDS, payload)


def _safe_remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:  # pragma: no cover - best effort cleanup
        logger.debug(
            "Failed to delete old chart",
            extra={"path": str(path), "error": str(exc)},
        )


def _build_chart(
    service: StatsService,
    window: StatsWindow,
    days: int,
) -> Optional[Path]:
    series = _series_for_window(service, window, days)
    if not series:
        return None

    dates, counts = zip(*series)
    highlight_index = len(counts) - 1

    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=150)
    fig.patch.set_facecolor(_DARK_BG)

    colors = [_BAR_COLOR] * len(counts)
    colors[highlight_index] = _PRIMARY_COLOR

    ax.bar(range(len(counts)), counts, color=colors, width=0.6)
    ax.set_xticks(range(len(counts)))
    ax.set_xticklabels([d.strftime("%d/%m") for d in dates], fontsize=9)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    max_value = max(counts)
    ax.set_ylim(0, max_value * 1.3 + 1 if max_value < 5 else max_value * 1.2)

    for idx, value in enumerate(counts):
        ax.text(
            idx,
            value + max_value * 0.05 + 0.2,
            f"{value}",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#fefeff",
        )

    ax.set_title("📊 Vendas (últimos 7 dias)", fontsize=13, pad=18, color="#fefeff")
    ax.set_ylabel("Vendas", fontsize=10)
    ax.set_xlabel("")

    for spine in ax.spines.values():
        spine.set_color(_DARK_BG)

    plt.tight_layout()

    tempdir = Path(tempfile.gettempdir())
    filename = tempdir / f"stats_chart_{service.owner_id}_{uuid.uuid4().hex}.png"
    fig.savefig(filename, dpi=150, bbox_inches="tight", facecolor=_DARK_BG)
    plt.close(fig)
    return filename


__all__ = ["ChartResult", "generate_sales_chart"]
