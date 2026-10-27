from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd

CATEGORIES = ["餐饮", "交通", "学习", "娱乐", "住房", "医疗", "订阅/会员", "购物", "人情/礼物", "其他"]
CATEGORY_KEYWORDS = [
    ("订阅/会员", ["会员", "订阅", "vip", "网盘", "音乐"]),
    ("住房", ["房租", "月租", "水费", "电费", "网费", "物业"]),
    ("人情/礼物", ["红包", "礼物", "请客", "礼金"]),
    ("学习", ["教材", "网课", "课程", "打印", "文具", "考证", "考试", "买书"]),
    ("交通", ["地铁", "公交", "打车", "滴滴", "单车", "车费", "高铁", "火车"]),
    ("医疗", ["买药", "挂号", "体检", "医院", "药费"]),
    ("娱乐", ["电影", "游戏", "ktv", "聚餐", "演出", "旅游"]),
    ("餐饮", ["饭", "早餐", "外卖", "奶茶", "咖啡", "零食", "水果", "食堂"]),
    ("购物", ["淘宝", "京东", "拼多多", "衣服", "鞋", "日用品"]),
]
FRAME_COLUMNS = ["id", "t_type", "amount", "t_time", "category", "note", "is_fixed"]


class ValidationError(ValueError):
    pass


def to_cents(value) -> int:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValidationError("金额需为有限的非负数字。")
        if amount > Decimal('1000000'):
            raise ValidationError("当前支持的单笔金额或预算上限为 100 万元。")
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("请填写有效金额。") from exc


def month_key(day: date) -> str:
    return day.strftime("%Y-%m")


def month_range(month: str) -> tuple[datetime, datetime]:
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValidationError("月份格式应为 YYYY-MM。")
    try:
        y, m = map(int, month.split("-"))
        start = datetime(y, m, 1)
        end = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
    except ValueError as exc:
        raise ValidationError("请选择有效月份。") from exc
    return start, end


@dataclass(frozen=True)
class Budget:
    month: str
    total: float
    fixed: float
    reserve: float

    def validate(self):
        month_range(self.month)
        total, fixed, reserve = (to_cents(x) for x in (self.total, self.fixed, self.reserve))
        if total <= 0:
            raise ValidationError("总预算需要大于 0。")
        if fixed + reserve > total:
            raise ValidationError("固定支出预算与预留金之和不能超过总预算。")


def as_frame(rows) -> pd.DataFrame:
    frame = pd.DataFrame([dict(r) for r in rows], columns=FRAME_COLUMNS)
    if not frame.empty:
        frame["t_time"] = pd.to_datetime(frame["t_time"], errors="coerce")
        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    return frame


def summarize(frame: pd.DataFrame, budget: Budget | None, month: str, today: date) -> dict:
    start, end = month_range(month)
    # Work from cents so totals do not inherit floating point rounding drift.
    def total(kind, fixed_only=False):
        if frame.empty:
            return 0.0
        selected = frame[frame["t_type"] == kind]
        if fixed_only:
            selected = selected[selected["is_fixed"].astype(bool)]
        return sum(to_cents(v) for v in selected["amount"]) / 100

    income, expense, fixed_spent = total("income"), total("expense"), total("expense", True)
    if today < start.date():
        remaining_days, phase = (end - start).days, "future"
    elif today >= end.date():
        remaining_days, phase = 0, "past"
    else:
        remaining_days, phase = (end.date() - today).days, "current"
    remaining = round(budget.total - expense, 2) if budget else None
    pending_fixed = round(max(budget.fixed - fixed_spent, 0), 2) if budget else 0
    flexible = max(round(remaining - budget.reserve - pending_fixed, 2), 0) if budget else None
    daily = round(flexible / remaining_days, 2) if budget and remaining_days else None
    return dict(income=income, expense=expense, balance=round(income - expense, 2),
                fixed_spent=fixed_spent, remaining=remaining, pending_fixed=pending_fixed,
                flexible=flexible, daily=daily, remaining_days=remaining_days, phase=phase,
                count=len(frame), progress=expense / budget.total if budget else None)


def category_stats(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["category", "amount", "share", "cumulative"])
    result = frame[frame["t_type"] == "expense"].groupby("category", as_index=False)["amount"].sum()
    result = result.sort_values("amount", ascending=False).reset_index(drop=True)
    total = result["amount"].sum()
    result["share"] = result["amount"] / total if total else 0.0
    result["cumulative"] = result["share"].cumsum()
    return result


def daily_trend(frame: pd.DataFrame, month: str) -> pd.DataFrame:
    start, end = month_range(month)
    out = pd.DataFrame({"day": pd.date_range(start, end - timedelta(days=1), freq="D")})
    for kind in ["expense", "income"]:
        if frame.empty:
            out[kind] = 0.0
        else:
            selected = frame[frame["t_type"] == kind].copy()
            grouped = selected.groupby(selected["t_time"].dt.normalize())["amount"].sum()
            out[kind] = out["day"].map(grouped).fillna(0.0)
    return out


def detect_anomalies(frame: pd.DataFrame, min_samples: int = 5) -> pd.DataFrame:
    result = frame.iloc[0:0].copy()
    result["threshold"] = pd.Series(dtype=float)
    result["sample_count"] = pd.Series(dtype=int)
    if frame.empty:
        return result
    expense = frame[frame["t_type"] == "expense"].copy()
    flagged = []
    for category, group in expense.groupby("category"):
        if len(group) < min_samples:
            continue
        median = float(group["amount"].median())
        mad = float((group["amount"] - median).abs().median())
        threshold = median + 5 * mad if mad > 0 else max(median * 2.5, median + 30)
        hits = group[(group["amount"] > threshold) & (group["amount"] >= 30)].copy()
        hits["threshold"] = round(threshold, 2)
        hits["sample_count"] = len(group)
        flagged.append(hits)
    if not flagged:
        return result
    return pd.concat(flagged, ignore_index=True).sort_values("amount", ascending=False)


def parse_entry(text: str, now: datetime) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise ValidationError("先写下一笔消费，例如：今天午饭 18 元。")
    work = raw
    entry_time = now.replace(microsecond=0)
    dates = re.findall(r"(?<!\d)\d{4}-\d{1,2}-\d{1,2}(?!\d)", raw)
    if len(dates) > 1:
        raise ValidationError("一次只记录一笔，请保留一个日期。")
    if dates:
        try:
            day = datetime.strptime(dates[0], "%Y-%m-%d").date()
            entry_time = datetime.combine(day, now.time().replace(microsecond=0))
        except ValueError as exc:
            raise ValidationError("日期无效，请核对后再解析。") from exc
        # Crucial: remove the date before extracting an amount.
        work = work.replace(dates[0], " ")
    elif "前天" in work:
        entry_time -= timedelta(days=2)
    elif "昨天" in work:
        entry_time -= timedelta(days=1)
    if re.search(r"[-−]\s*\d", work):
        raise ValidationError("金额请填写正数；退款可写为“退款收入 20 元”。")
    amounts = re.findall(r"(?<![\d.])(?:\d+(?:\.\d+)?|\.\d+)(?![\d.])", work)
    if len(amounts) != 1:
        raise ValidationError("请只保留一个金额，例如“奶茶 15 元”；多笔记录请分开输入。")
    amount = to_cents(amounts[0]) / 100
    if amount <= 0:
        raise ValidationError("金额需要大于 0。")
    lowered = raw.lower()
    kind = "income" if any(x in lowered for x in ["收入", "工资", "奖学金", "兼职", "返现", "报销", "生活费", "退款"]) else "expense"
    if "支出" in raw:
        kind = "expense"
    category = next((cat for cat, keys in CATEGORY_KEYWORDS if any(k in lowered for k in keys)), "其他")
    fixed = kind == "expense" and any(x in lowered for x in ["房租", "月租", "水费", "电费", "网费", "会员", "订阅", "vip"])
    return dict(t_type=kind, amount=amount, t_time=entry_time, category=category, note=raw, is_fixed=fixed)

