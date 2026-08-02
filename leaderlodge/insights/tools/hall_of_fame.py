from __future__ import annotations

from leaderlodge.games.registry import score_direction_label
from leaderlodge.groups.models import Group
from leaderlodge.leaderboards.hall_of_fame import (
    GRANULARITY_MONTH,
    GRANULARITY_YEAR,
    build_hall_of_fame_grid,
    resolve_hall_of_fame_granularity,
)


def query_hall_of_fame(
    group: Group,
    *,
    granularity: str = GRANULARITY_YEAR,
    game_type_code: str | None = None,
    limit: int = 20,
) -> dict:
    resolved = resolve_hall_of_fame_granularity(granularity)
    grid = build_hall_of_fame_grid(group, granularity=resolved)

    columns = grid.columns
    if game_type_code is not None:
        columns = tuple(col for col in columns if col.code == game_type_code)

    total_periods = len(grid.rows)
    rows = []
    for row in grid.rows[:limit]:
        cells = []
        for column, cell in zip(grid.columns, row.cells, strict=True):
            if game_type_code is not None and column.code != game_type_code:
                continue
            cells.append(
                {
                    "game_type_code": column.code,
                    "game_type_name": column.name,
                    "score_direction": score_direction_label(column.code),
                    "leader": cell.player_label or None,
                    "player_id": cell.player_id,
                    "rank_score": (
                        round(cell.rank_score, 2)
                        if cell.rank_score is not None
                        else None
                    ),
                }
            )
        rows.append(
            {
                "period_label": row.label,
                "year": row.period.year,
                "month": row.period.month,
                "leaders": cells,
            }
        )

    payload = {
        "group_id": group.pk,
        "group_name": group.name,
        "granularity": resolved,
        "granularity_label": "Months" if resolved == GRANULARITY_MONTH else "Years",
        "game_type_code": game_type_code,
        "periods": rows,
        "periods_returned": len(rows),
        "periods_available": total_periods,
    }
    if total_periods > len(rows):
        omitted = total_periods - len(rows)
        unit = "months" if resolved == GRANULARITY_MONTH else "years"
        payload["truncated"] = True
        payload["truncation_note"] = (
            f"Periods are ordered most-recent-first. Showing the {len(rows)} "
            f"most recent {unit} of {total_periods} total; the {omitted} "
            f"oldest {unit} are omitted. You must tell the user this data is "
            "incomplete and state the total and omitted counts; do not "
            "silently answer as if this were the full history."
        )
    else:
        payload["truncated"] = False
    return payload
