"""
PlanRepository — gateway_db.plans access.

get() never fails for a known plan name: if its row is missing (fresh DB
before seeding) it falls back to the code defaults in app.Config.PLANS.
Unknown names resolve to the default plan, so a typo in users.plan can't
lock anyone out or hand out unlimited usage.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.Config import DEFAULT_PLAN, PLAN_LIMIT_FIELDS, PLANS
from app.Entities import Plan


def plan_dict(row: Plan) -> dict:
    return {
        "name": row.name,
        "available": bool(row.available),
        "price_cents_monthly": int(row.price_cents_monthly or 0),
        "currency": row.currency or "usd",
        **{field: int(getattr(row, field)) for field in PLAN_LIMIT_FIELDS},
    }


class PlanRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_row(self, name: str) -> Optional[Plan]:
        result = await self.db.execute(select(Plan).where(Plan.name == name))
        return result.scalar_one_or_none()

    async def get(self, name: Optional[str]) -> dict:
        """The plan's limits as a dict. Unknown plan names fall back to the default plan."""
        name = (name or DEFAULT_PLAN).strip().lower()
        row = await self.get_row(name)
        if row is None and name not in PLANS:
            name = DEFAULT_PLAN
            row = await self.get_row(name)
        if row is not None:
            return plan_dict(row)
        return dict(PLANS.get(name) or PLANS[DEFAULT_PLAN])

    async def all(self) -> list[dict]:
        """Every plan: the code-defined ones first, in their order, then any extra rows."""
        rows = {p.name: p for p in (await self.db.execute(select(Plan))).scalars().all()}
        out = [plan_dict(rows[n]) if n in rows else dict(PLANS[n]) for n in PLANS]
        out += [plan_dict(rows[n]) for n in sorted(rows) if n not in PLANS]
        return out

    async def seed_missing(self) -> list[str]:
        """Insert a row for each code-defined plan that has none. Never overwrites an existing row."""
        existing = set((await self.db.execute(select(Plan.name))).scalars().all())
        added = []
        for name, plan in PLANS.items():
            if name in existing:
                continue
            self.db.add(Plan(**plan))
            added.append(name)
        if added:
            await self.db.flush()
        return added
