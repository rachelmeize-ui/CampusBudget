from datetime import datetime

import pytest

from campusbudget import storage
from campusbudget.core import Budget, ValidationError


def sample(**changes):
    e=dict(t_type='expense',amount=18.5,t_time=datetime(2026,10,27,12),category='餐饮',note='午饭',is_fixed=False)
    return e | changes


def test_storage_round_trip_and_month_filter(tmp_path):
    path=tmp_path/'test.db'
    conn=storage.connect(path)
    storage.add_entry(conn,**sample())
    storage.add_entry(conn,**sample(t_time=datetime(2026,9,30)))
    assert len(storage.list_entries(conn,'2026-10'))==1
    assert storage.list_entries(conn,'2026-10')[0]['amount']==18.5
    conn.close()
    reopened=storage.connect(path)
    assert len(storage.list_entries(reopened))==2
    reopened.close()


def test_invalid_batch_is_atomic():
    conn=storage.connect()
    with pytest.raises(ValidationError): storage.add_entries(conn,[sample(),sample(amount=-5)])
    assert len(storage.list_entries(conn))==0
    conn.close()


def test_budget_upsert_and_delete():
    conn=storage.connect()
    storage.save_budget(conn,Budget('2026-10',1000,300,100))
    storage.save_budget(conn,Budget('2026-10',2000,500,200))
    assert storage.get_budget(conn,'2026-10').total==2000
    entry_id=storage.add_entry(conn,**sample())
    assert storage.delete_entry(conn,entry_id)
    assert not storage.delete_entry(conn,entry_id)
    conn.close()


def test_income_cannot_be_counted_as_fixed_expense():
    conn=storage.connect()
    storage.add_entry(conn,**sample(t_type='income',is_fixed=True))
    assert storage.list_entries(conn)[0]['is_fixed']==0
    conn.close()


def test_demo_and_personal_connections_are_isolated(tmp_path):
    demo=storage.connect()
    personal=storage.connect(tmp_path/'personal.db')
    storage.add_entry(demo,**sample())
    assert len(storage.list_entries(personal))==0
    demo.close();personal.close()
