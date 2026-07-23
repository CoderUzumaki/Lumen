"""Scheduled briefing generation (BRIEF-03).

APScheduler job that fires every 15 minutes and generates a fresh briefing
for every user whose *local* hour matches their `user_preferences.briefing_hour`
AND who doesn't yet have a briefing for their local date.

Concurrency is capped at 5 concurrent generations via `asyncio.Semaphore(5)`
— BRIEF-02's `synthesize_briefing_for_user` is idempotent on
`(user_id, portfolio_id, briefing_date)`, so a run that races with itself
(e.g. two 15-minute ticks in the same hour) never persists duplicate rows.

`briefing_date` is the user's LOCAL date at scheduler-tick time, not UTC — a
user at `briefing_hour=8, briefing_timezone="Asia/Kolkata"` gets a briefing
generated around 08:00 IST for the IST calendar date, even though the tick
fires at 02:30 UTC.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Coroutine, Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.briefing.graph import synthesize_briefing_for_user
from app.db.models.briefing import Briefing
from app.db.models.portfolio import Portfolio
from app.db.models.user_preferences import UserPreferences
from app.utils.llm import LLMClient

log = logging.getLogger(__name__)


# BRIEF-03: bounded concurrency for the fan-out. BRIEF-02 does thorough-tier
# LLM calls — running 5 in flight is plenty for the free-tier RPM budget.
_MAX_CONCURRENCY = 5


@dataclass
class BriefingSchedulerSummary:
    """Aggregate counts for one scheduler tick."""

    candidates_considered: int = 0
    generated: int = 0
    skipped_already_exists: int = 0
    skipped_no_active_portfolio: int = 0
    skipped_unknown_timezone: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    generated_briefing_ids: list[UUID] = field(default_factory=list)


# Type alias for the callable that actually synthesizes a briefing. Tests
# override via the `synthesizer` kwarg so they can bypass the real graph.
SynthesizerFn = Callable[
    [UUID, UUID, "AsyncSession", LLMClient, Any],
    Coroutine[Any, Any, Briefing | None],
]


async def _default_synthesizer(
    user_id: UUID,
    portfolio_id: UUID,
    session: AsyncSession,
    llm: LLMClient,
    briefing_date,
) -> Briefing | None:
    return await synthesize_briefing_for_user(
        user_id,
        portfolio_id,
        session=session,
        llm=llm,
        briefing_date=briefing_date,
    )


def _user_local_hour_matches(
    pref: UserPreferences, now_utc: datetime
) -> tuple[bool, "date" | None]:
    """Return `(matches, user_local_date)`.

    `matches` is True iff the user's local wall-clock hour at `now_utc` equals
    their configured `briefing_hour`. `user_local_date` is the same local
    moment's date component (used for the idempotency check + briefing_date).
    """
    try:
        tz = ZoneInfo(pref.briefing_timezone or "UTC")
    except ZoneInfoNotFoundError:
        log.warning(
            "briefing_scheduler: unknown timezone %r for user=%s; skipping",
            pref.briefing_timezone,
            pref.user_id,
        )
        return (False, None)
    local = now_utc.astimezone(tz)
    return (local.hour == pref.briefing_hour, local.date())


async def _briefing_exists_for(
    session: AsyncSession,
    *,
    user_id: UUID,
    portfolio_id: UUID,
    briefing_date,
) -> bool:
    row = (
        await session.execute(
            select(Briefing.id).where(
                Briefing.user_id == user_id,
                Briefing.portfolio_id == portfolio_id,
                Briefing.briefing_date == briefing_date,
            )
        )
    ).scalar_one_or_none()
    return row is not None


async def _active_portfolio_id(
    session: AsyncSession, user_id: UUID
) -> UUID | None:
    return (
        await session.execute(
            select(Portfolio.id).where(
                Portfolio.user_id == user_id,
                Portfolio.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


async def _run_one(
    *,
    user_id: UUID,
    portfolio_id: UUID,
    briefing_date,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMClient,
    semaphore: asyncio.Semaphore,
    synthesizer: SynthesizerFn,
    summary: BriefingSchedulerSummary,
) -> None:
    async with semaphore:
        try:
            async with session_factory() as session:
                row = await synthesizer(
                    user_id, portfolio_id, session, llm, briefing_date
                )
                if row is not None:
                    summary.generated += 1
                    summary.generated_briefing_ids.append(row.id)
        except Exception:  # noqa: BLE001 — background task must never leak
            log.exception(
                "briefing_scheduler: synthesize failed user=%s portfolio=%s",
                user_id,
                portfolio_id,
            )
            summary.errors += 1


async def run_briefing_scheduler(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMClient,
    now: datetime | None = None,
    concurrency: int = _MAX_CONCURRENCY,
    synthesizer: SynthesizerFn = _default_synthesizer,
) -> BriefingSchedulerSummary:
    """Run one scheduler tick.

    - Loads every `UserPreferences` row.
    - Filters by (a) `local_hour == briefing_hour`, (b) an active portfolio
      exists, (c) no `briefing` row already for the user's local date.
    - Runs the surviving candidates through `synthesizer` under an
      `asyncio.Semaphore(concurrency)`.
    """
    started = time.monotonic()
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    summary = BriefingSchedulerSummary()

    # Enumerate all users with preferences in ONE query. The active-portfolio
    # + already-exists checks happen per-user below with their own sessions.
    async with session_factory() as session:
        prefs = list(
            (await session.execute(select(UserPreferences))).scalars().all()
        )

    if not prefs:
        summary.elapsed_seconds = time.monotonic() - started
        log.info("briefing_scheduler: no user preferences configured")
        return summary

    semaphore = asyncio.Semaphore(max(1, concurrency))
    tasks: list[asyncio.Task] = []

    for pref in prefs:
        matches, local_date = _user_local_hour_matches(pref, now_utc)
        if local_date is None:
            summary.skipped_unknown_timezone += 1
            continue
        if not matches:
            continue

        summary.candidates_considered += 1

        # Per-user pre-flight (own session) to avoid double work.
        async with session_factory() as session:
            portfolio_id = await _active_portfolio_id(session, pref.user_id)
            if portfolio_id is None:
                summary.skipped_no_active_portfolio += 1
                log.debug(
                    "briefing_scheduler: user=%s has no active portfolio",
                    pref.user_id,
                )
                continue
            if await _briefing_exists_for(
                session,
                user_id=pref.user_id,
                portfolio_id=portfolio_id,
                briefing_date=local_date,
            ):
                summary.skipped_already_exists += 1
                continue

        tasks.append(
            asyncio.create_task(
                _run_one(
                    user_id=pref.user_id,
                    portfolio_id=portfolio_id,
                    briefing_date=local_date,
                    session_factory=session_factory,
                    llm=llm,
                    semaphore=semaphore,
                    synthesizer=synthesizer,
                    summary=summary,
                )
            )
        )

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=False)

    summary.elapsed_seconds = time.monotonic() - started
    log.info(
        "briefing_scheduler_done considered=%d generated=%d "
        "skipped_existing=%d skipped_no_portfolio=%d skipped_bad_tz=%d "
        "errors=%d elapsed=%.2fs",
        summary.candidates_considered,
        summary.generated,
        summary.skipped_already_exists,
        summary.skipped_no_active_portfolio,
        summary.skipped_unknown_timezone,
        summary.errors,
        summary.elapsed_seconds,
    )
    return summary
