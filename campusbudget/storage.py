from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .core import Budget, CATEGORIES, ValidationError, month_range, to_cents


def local_path() -> Path:
    return Path(os.environ.get("CAMPUSBUDGET_DB", Path(__file__).resolve().parents[1] / "data" / "budget.db"))


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS entries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      t_type TEXT NOT NULL CHECK(t_type IN ('income','expense')),
      amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
      t_time TEXT NOT NULL, category TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '', is_fixed INTEGER NOT NULL DEFAULT 0 CHECK(is_fixed IN (0,1))
    );
    CREATE INDEX IF NOT EXISTS ix_entries_time ON entries(t_time);
    CREATE TABLE IF NOT EXISTS budgets (
      month TEXT PRIMARY KEY, total_cents INTEGER NOT NULL CHECK(total_cents>0),
      fixed_cents INTEGER NOT NULL CHECK(fixed_cents>=0),
      reserve_cents INTEGER NOT NULL CHECK(reserve_cents>=0),
      CHECK(fixed_cents+reserve_cents<=total_cents)
    );
    """)
    return conn


def validate_entry(entry: dict) -> tuple:
    if entry.get("t_type") not in ["income", "expense"]:
        raise ValidationError("请选择收入或支出。")
    if entry.get("category") not in CATEGORIES:
        raise ValidationError("请选择有效分类。")
    cents = to_cents(entry.get("amount"))
    if cents <= 0:
        raise ValidationError("金额需要大于 0。")
    when = entry.get("t_time")
    if not isinstance(when, datetime):
        raise ValidationError("请选择有效日期。")
    return (entry["t_type"], cents, when.isoformat(timespec="seconds"), entry["category"],
            str(entry.get("note") or "").strip()[:500], int(bool(entry.get("is_fixed")) and entry["t_type"]=="expense"))


def add_entry(conn: sqlite3.Connection, **entry) -> int:
    values = validate_entry(entry)
    with conn:
        cursor = conn.execute("INSERT INTO entries(t_type,amount_cents,t_time,category,note,is_fixed) VALUES(?,?,?,?,?,?)", values)
    return int(cursor.lastrowid)


def add_entries(conn: sqlite3.Connection, entries: list[dict]) -> int:
    # Validate the whole batch before changing the ledger.
    values = [validate_entry(e) for e in entries]
    with conn:
        conn.executemany("INSERT INTO entries(t_type,amount_cents,t_time,category,note,is_fixed) VALUES(?,?,?,?,?,?)",values)
    return len(values)


def list_entries(conn: sqlite3.Connection, month: str | None = None):
    sql = "SELECT id,t_type,amount_cents/100.0 AS amount,t_time,category,note,is_fixed FROM entries"
    args = ()
    if month:
        start,end = month_range(month)
        sql += " WHERE t_time>=? AND t_time<?"
        args=(start.isoformat(timespec="seconds"),end.isoformat(timespec="seconds"))
    return conn.execute(sql+" ORDER BY t_time DESC,id DESC",args).fetchall()


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    with conn:
        result = conn.execute("DELETE FROM entries WHERE id=?",(entry_id,))
    return result.rowcount == 1


def save_budget(conn: sqlite3.Connection, budget: Budget):
    budget.validate()
    with conn:
        conn.execute("INSERT INTO budgets VALUES(?,?,?,?) ON CONFLICT(month) DO UPDATE SET total_cents=excluded.total_cents,fixed_cents=excluded.fixed_cents,reserve_cents=excluded.reserve_cents",
                     (budget.month,to_cents(budget.total),to_cents(budget.fixed),to_cents(budget.reserve)))


def get_budget(conn: sqlite3.Connection, month: str) -> Budget | None:
    row=conn.execute("SELECT * FROM budgets WHERE month=?",(month,)).fetchone()
    return Budget(row['month'],row['total_cents']/100,row['fixed_cents']/100,row['reserve_cents']/100) if row else None


def months(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT substr(t_time,1,7) AS month FROM entries UNION SELECT month FROM budgets ORDER BY month DESC")]
