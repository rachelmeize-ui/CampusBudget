from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from campusbudget import storage, ui, views
from campusbudget.core import month_key
from campusbudget.demo import seed_demo

st.set_page_config(page_title='CampusBudget · 校园预算助手',page_icon='💳',layout='wide',initial_sidebar_state='auto')
ui.apply_styles()
today=datetime.now(ZoneInfo('Asia/Shanghai')).date()


def navigate(name):
    st.session_state['navigation']=name


with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">CB</div><div><div class="brand-name">CampusBudget</div><div class="brand-sub">把生活费，安排明白</div></div></div>',unsafe_allow_html=True)
    st.markdown('<div class="nav-overline">我的生活账本</div>',unsafe_allow_html=True)
    nav=st.radio('页面', ['总览看板','记一笔','消费分析','预算管理','账本管理'],key='navigation',label_visibility='collapsed')
    st.divider()
    public_demo=os.environ.get('CAMPUSBUDGET_PUBLIC_DEMO')=='1'
    options=['演示账本'] if public_demo else ['演示账本','本地账本']
    mode=st.selectbox('当前账本',options,key='ledger_mode')
    is_demo=mode=='演示账本'
    st.markdown('<div class="ledger-pill">'+('演示数据 · 当前会话独立' if is_demo else '个人记录 · 本机保存')+'</div>',unsafe_allow_html=True)

connection_key='_demo_connection' if is_demo else '_local_connection'
if connection_key not in st.session_state:
    conn=storage.connect(':memory:' if is_demo else storage.local_path())
    if is_demo:
        seed_demo(conn,today)
    st.session_state[connection_key]=conn
conn=st.session_state[connection_key]

with st.sidebar:
    if is_demo:
        st.caption('可以自由记账和修改预算。这里的记录全部是模拟数据，不会写入你的本地账本。')
        if st.button('重置演示账本',use_container_width=True):
            conn.close()
            del st.session_state[connection_key]
            st.session_state.pop('_parsed_entry',None)
            st.session_state['_entry_generation']=st.session_state.get('_entry_generation',0)+1
            st.rerun()
    else:
        st.caption('记录保存在当前电脑；演示账本与个人记录相互独立。')
    st.markdown('<div class="sidebar-note">少一点月底的猜测<br>多一点日常的从容<br><br>LOCAL FIRST · BUILT WITH CARE</div>',unsafe_allow_html=True)

month_options=sorted(set(storage.months(conn)+[month_key(today)]),reverse=True)
if st.session_state.get('selected_month') not in month_options:
    st.session_state['selected_month']=month_key(today)

left,right=st.columns([.78,.22],vertical_alignment='bottom')
descriptions={
    '总览看板':('这个月，花得心里有数。','看见收支的节奏，把预算留给真正重要的事。'),
    '记一笔':('记下这一笔，轻松一点。','输入一句话，或填写一张小表单。保存前，信息由你确认。'),
    '消费分析':('钱花在哪里，一眼看清。','从消费结构和日常趋势里，找到适合自己的花钱节奏。'),
    '预算管理':('给生活留一点余地。','安排日常开销，也为固定支出和临时计划留出空间。'),
    '账本管理':('每一笔，都有记录。','筛选、导出和整理自己的收支明细。'),
}
with left:
    ui.heading(*descriptions[nav])
with right:
    month=st.selectbox('查看月份',month_options,format_func=lambda m:f'{m[:4]} 年 {int(m[5:])} 月',key='selected_month')

flash=st.session_state.pop('_flash',None)
if flash:
    st.success(flash)

dispatch={'总览看板':views.dashboard,'记一笔':views.entry,'消费分析':views.analytics,'预算管理':views.budget,'账本管理':views.ledger}
dispatch[nav](conn,month,today,navigate,is_demo)
st.markdown('<div class="footer-note"><span>CampusBudget · 让日常预算更清楚</span><span>'+('当前为模拟数据，可放心体验' if is_demo else '个人账本保存在当前设备')+'</span></div>',unsafe_allow_html=True)

