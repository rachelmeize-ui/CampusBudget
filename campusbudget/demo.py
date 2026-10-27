from __future__ import annotations

import calendar
import random
from datetime import date, datetime, timedelta

from . import storage
from .core import Budget, month_key


def seed_demo(conn, today: date):
    """Deterministic synthetic data. Does not read the author's original ledger."""
    rng = random.Random(2026)
    notes = {"餐饮": ["食堂午餐", "早餐与水果", "周末咖啡"], "交通": ["地铁出行", "共享单车"],
             "学习": ["课程教材", "打印资料"], "娱乐": ["周末电影", "和朋友桌游"],
             "购物": ["生活用品", "换季衣物"]}
    first = today.replace(day=1)
    for offset in [-1, 0]:
        start = (first-timedelta(days=1)).replace(day=1) if offset == -1 else first
        last = calendar.monthrange(start.year,start.month)[1] if offset == -1 else today.day
        month = month_key(start)
        storage.save_budget(conn,Budget(month,3200,650,300))
        storage.add_entry(conn,t_type="income",amount=3500,t_time=datetime(start.year,start.month,1,9),category="其他",note="演示 · 本月生活费",is_fixed=False)
        for day in range(1,last+1):
            when=datetime(start.year,start.month,day,12,10)
            for i in range(2):
                storage.add_entry(conn,t_type="expense",amount=round(rng.uniform(10,23),2),t_time=when+timedelta(hours=i*6),category="餐饮",note=rng.choice(notes['餐饮']),is_fixed=False)
            if day%3==0:
                cat=rng.choice(["交通","学习","娱乐","购物"])
                amount=rng.uniform(2,12) if cat=="交通" else rng.uniform(18,62)
                storage.add_entry(conn,t_type="expense",amount=round(amount,2),t_time=when+timedelta(hours=3),category=cat,note=rng.choice(notes[cat]),is_fixed=False)
            if day%4==0:
                storage.add_entry(conn,t_type="expense",amount=8,t_time=when+timedelta(hours=2),category="交通",note="地铁往返",is_fixed=False)
        storage.add_entry(conn,t_type="expense",amount=600,t_time=datetime(start.year,start.month,1,10),category="住房",note="演示 · 宿舍费用",is_fixed=True)
        if last>=5:
            storage.add_entry(conn,t_type="expense",amount=25,t_time=datetime(start.year,start.month,5,9),category="订阅/会员",note="演示 · 月度订阅",is_fixed=True)
        if last>=9:
            storage.add_entry(conn,t_type="expense",amount=188,t_time=datetime(start.year,start.month,min(last,19),19),category="餐饮",note="演示 · 和朋友聚餐（观察提醒）",is_fixed=False)
        if last>=15:
            storage.add_entry(conn,t_type="income",amount=350,t_time=datetime(start.year,start.month,15,18),category="其他",note="演示 · 兼职收入",is_fixed=False)
