from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

COLORS = ["#355d7b", "#76cbb0", "#b9c9d8", "#d8bb86", "#9aacc2", "#accfca", "#b6b0cb", "#d4dce5", "#bccca7", "#d8c4b9"]


def apply_styles():
    st.markdown('<style>'+(Path(__file__).resolve().parents[1]/'assets'/'style.css').read_text(encoding='utf-8')+'</style>',unsafe_allow_html=True)


def heading(title, description, eyebrow="CAMPUSBUDGET / YOUR EVERYDAY BALANCE"):
    st.markdown(f'<div class="eyebrow">{escape(eyebrow)}</div><h1 class="page-heading">{escape(title)}</h1><p class="page-description">{escape(description)}</p>',unsafe_allow_html=True)


def section(title, note=""):
    st.markdown(f'<div class="section-heading">{escape(title)}</div><div class="section-note">{escape(note)}</div>',unsafe_allow_html=True)


def money(value, digits=2):
    return '—' if value is None else f'{value:,.{digits}f}'


def stat_card(label, value, foot, icon="↗", style=""):
    st.markdown(f'<div class="stat-card {escape(style)}"><div class="stat-label">{escape(label)}<span class="stat-icon">{escape(icon)}</span></div><div class="stat-value"><span class="currency">¥</span>{money(value)}</div><div class="stat-foot">{escape(foot)}</div></div>',unsafe_allow_html=True)


def insight(title, text, warn=False, icon="i"):
    st.markdown(f'<div class="insight {"warn" if warn else ""}"><div class="insight-tag">{escape(icon)}</div><div><p class="insight-title">{escape(title)}</p><p class="insight-text">{escape(text)}</p></div></div>',unsafe_allow_html=True)


def empty(title="还没有记录", text="从记下第一笔开始，慢慢看清自己的消费节奏。"):
    st.markdown(f'<div class="empty-state"><strong>{escape(title)}</strong><p>{escape(text)}</p></div>',unsafe_allow_html=True)


def budget_card(summary, budget):
    if not budget:
        st.markdown('<div class="budget-panel"><div class="mini-title">给生活费一点安排</div><h3>先定一个小目标</h3><div class="budget-note">设好本月预算，就能看到剩余额度和每日可用金额。</div><div class="budget-divider"></div><div class="budget-note">不追求每一笔都完美，先从心里有数开始。</div></div>',unsafe_allow_html=True)
        return
    progress=min(max(summary['progress'],0),1)*100
    daily_label = "每日可用参考" if summary['phase']!='past' else "历史月份 · 已结算"
    remaining_label = money(summary['daily']) if summary['daily'] is not None else '—'
    st.markdown(f'''<div class="budget-panel"><div class="mini-title">{daily_label}</div><h3>¥ {remaining_label}</h3>
    <div class="budget-note">已扣除预留金和待发生的固定支出预算</div>
    <div class="progress-track"><div class="progress-fill" style="width:{progress}%"></div></div>
    <div class="progress-labels"><span>已使用 {summary['progress']:.0%}</span><span>预算 ¥ {money(budget.total,0)}</span></div>
    <div class="budget-divider"></div><div class="budget-detail"><span>剩余预算</span><strong>¥ {money(summary['remaining'])}</strong></div>
    <div class="budget-detail"><span>预留金</span><strong>¥ {money(budget.reserve)}</strong></div>
    <div class="budget-detail"><span>待发生的固定支出</span><strong>¥ {money(summary['pending_fixed'])}</strong></div></div>''',unsafe_allow_html=True)


def chart_style(fig, height=260):
    fig.update_layout(height=height,margin=dict(l=10,r=12,t=18,b=10),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(family='Segoe UI, Microsoft YaHei, sans-serif',size=11,color='#8293a5'),legend=dict(orientation='h',y=1.12,x=1,xanchor='right',font=dict(size=10)),hoverlabel=dict(bgcolor='white',font_size=12),dragmode=False)
    fig.update_xaxes(showgrid=False,zeroline=False,title=None)
    fig.update_yaxes(gridcolor='#eef2f6',zeroline=False,title=None)
    return fig


def trend_chart(trend, income=False):
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=trend['day'],y=trend['expense'],name='支出',mode='lines',line=dict(color='#355d7b',width=2.6,shape='spline',smoothing=.5),fill='tozeroy',fillcolor='rgba(53,93,123,.075)',hovertemplate='%{x|%m月%d日}<br>支出 ¥%{y:,.2f}<extra></extra>'))
    if income:
        fig.add_trace(go.Scatter(x=trend['day'],y=trend['income'],name='收入',mode='lines',line=dict(color='#76cbb0',width=2,dash='dot'),hovertemplate='%{x|%m月%d日}<br>收入 ¥%{y:,.2f}<extra></extra>'))
    chart_style(fig)
    fig.update_xaxes(dtick=5*86400000,tickformat='%m.%d')
    fig.update_yaxes(tickprefix='¥ ',rangemode='tozero',nticks=4)
    return fig


def donut_chart(categories):
    fig=go.Figure(go.Pie(labels=categories['category'],values=categories['amount'],hole=.74,sort=False,marker=dict(colors=COLORS,line=dict(color='white',width=3)),textinfo='none',hovertemplate='%{label}<br>¥%{value:,.2f} · %{percent}<extra></extra>'))
    chart_style(fig,260)
    fig.update_layout(showlegend=False,annotations=[dict(text='消费结构',x=.5,y=.55,showarrow=False,font=dict(size=11,color='#9ba7b4')),dict(text=f"{len(categories)} 类",x=.5,y=.42,showarrow=False,font=dict(size=23,color='#284b66'))])
    return fig


def ledger_table(frame, limit=None):
    if frame.empty:
        empty()
        return
    show=frame.head(limit).copy() if limit else frame.copy()
    show['日期']=show['t_time'].dt.strftime('%m-%d %H:%M')
    show['类型']=show['t_type'].map({'expense':'支出','income':'收入'})
    show['分类']=show['category']
    show['金额']=show['amount']
    show['备注']=show['note'].fillna('')
    show['固定支出']=show['is_fixed'].map({0:'否',1:'是'})
    st.dataframe(show[['日期','类型','分类','金额','备注','固定支出']],hide_index=True,use_container_width=True,column_config={'金额':st.column_config.NumberColumn('金额 / 元',format='%.2f'),'备注':st.column_config.TextColumn('备注',width='large')})

