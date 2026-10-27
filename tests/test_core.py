from datetime import date, datetime

import pytest

from campusbudget.core import Budget, ValidationError, as_frame, detect_anomalies, month_range, parse_entry, summarize, to_cents

NOW=datetime(2026,10,27,12,0)


def frame(amounts, category='餐饮'):
    return as_frame([dict(id=i,t_type='expense',amount=x,t_time='2026-10-20T12:00:00',category=category,note='',is_fixed=0) for i,x in enumerate(amounts)])


def test_date_not_misread_as_amount():
    record=parse_entry('2026-05-10 奶茶 15',NOW)
    assert record['amount']==15
    assert record['t_time'].date()==date(2026,5,10)
    assert record['category']=='餐饮'


@pytest.mark.parametrize('text',['2026-02-30 午饭18','午饭18晚饭20','奶茶 -15','奶茶0','没有金额','会员 3个月 30元','收入999999999999999999999'])
def test_ambiguous_or_invalid_entry_is_not_silently_saved(text):
    with pytest.raises(ValidationError): parse_entry(text,NOW)


def test_relative_date_and_income():
    assert parse_entry('昨天兼职收入300',NOW)['t_time'].date()==date(2026,10,26)
    assert parse_entry('昨天兼职收入300',NOW)['t_type']=='income'
    assert parse_entry('会员25元',NOW)['is_fixed'] is True
    assert parse_entry('奶茶 .5 元',NOW)['amount']==.5


def test_month_boundaries_and_leap_year():
    assert month_range('2024-02')==(datetime(2024,2,1),datetime(2024,3,1))
    assert month_range('2026-12')[1]==datetime(2027,1,1)
    with pytest.raises(ValidationError): month_range('2026-13')


def test_money_rounding_and_nonfinite():
    assert to_cents('1.005')==101
    with pytest.raises(ValidationError): to_cents(float('nan'))
    with pytest.raises(ValidationError): to_cents(-2)


def test_budget_constraints():
    with pytest.raises(ValidationError): Budget('2026-10',100,90,20).validate()
    with pytest.raises(ValidationError): Budget('2026-10',0,0,0).validate()


def test_current_allowance_reserves_pending_fixed_and_includes_today():
    summary=summarize(frame([100]),Budget('2026-10',1000,300,100),'2026-10',date(2026,10,27))
    assert summary['remaining_days']==5
    assert summary['remaining']==900
    assert summary['pending_fixed']==300
    assert summary['daily']==100


def test_historical_month_has_no_current_day_allowance():
    s=summarize(frame([100]),Budget('2026-09',1000,100,100),'2026-09',date(2026,10,27))
    assert s['phase']=='past' and s['remaining_days']==0 and s['daily'] is None


def test_future_month_uses_its_own_length():
    s=summarize(as_frame([]),Budget('2027-02',2800,0,0),'2027-02',date(2026,10,27))
    assert s['remaining_days']==28 and s['daily']==100


def test_missing_budget_and_overspend():
    assert summarize(frame([1]),None,'2026-10',date(2026,10,27))['daily'] is None
    assert summarize(frame([2000]),Budget('2026-10',1000,0,0),'2026-10',date(2026,10,27))['daily']==0


def test_mad_flags_outlier_and_handles_zero_mad():
    hits=detect_anomalies(frame([18,20,20,21,22,188]))
    assert hits['amount'].tolist()==[188]
    assert hits.iloc[0]['threshold']==25.5
    assert detect_anomalies(frame([20,20,20,20,20,120]))['amount'].tolist()==[120]


def test_small_categories_do_not_generate_confident_alerts():
    assert detect_anomalies(frame([15,2000])).empty

