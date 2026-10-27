from pathlib import Path

from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'


def test_all_views_render_and_parser_requires_confirmation(monkeypatch):
    monkeypatch.setenv('CAMPUSBUDGET_PUBLIC_DEMO','1')
    app=AppTest.from_file(str(APP),default_timeout=25).run()
    assert not app.exception
    before=app.session_state['_demo_connection'].execute('SELECT count(*) FROM entries').fetchone()[0]
    for view in ['记一笔','消费分析','预算管理','账本管理']:
        app.radio(key='navigation').set_value(view).run()
        assert not app.exception, view
    app.radio(key='navigation').set_value('记一笔').run()
    app.text_area(key='entry_text').set_value('2026-05-10 奶茶 15').run()
    next(b for b in app.button if b.label=='解析这笔记录').click().run()
    assert not app.exception
    assert app.session_state['_parsed_entry']['amount']==15
    after=app.session_state['_demo_connection'].execute('SELECT count(*) FROM entries').fetchone()[0]
    assert before==after
    next(b for b in app.button if b.label=='确认并保存').click().run()
    assert not app.exception
    assert app.session_state['_demo_connection'].execute('SELECT count(*) FROM entries').fetchone()[0]==before+1

