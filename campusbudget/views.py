from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from . import storage, ui
from .core import Budget, CATEGORIES, ValidationError, as_frame, category_stats, daily_trend, detect_anomalies, month_range, parse_entry, summarize


def context(conn,month,today):
    frame=as_frame(storage.list_entries(conn,month))
    budget=storage.get_budget(conn,month)
    return frame,budget,summarize(frame,budget,month,today)


def dashboard(conn,month,today,navigate,is_demo):
    frame,plan,summary=context(conn,month,today)
    cards=st.columns(4,gap='medium')
    with cards[0]: ui.stat_card('本月支出',summary['expense'],f"已记录 {len(frame[frame['t_type']=='expense']) if not frame.empty else 0} 笔消费",'↗','primary')
    with cards[1]: ui.stat_card('本月收入',summary['income'],'生活费、兼职与其他收入','↓')
    with cards[2]: ui.stat_card('收支结余',summary['balance'],'本月收入 − 本月支出','≈','mint')
    with cards[3]: ui.stat_card('剩余预算',summary['remaining'],'已结算的历史月份' if summary['phase']=='past' else ('还剩 '+str(summary['remaining_days'])+' 天' if plan else '设置预算后查看'),'◷')
    st.write('')
    main,aside=st.columns([1.85,1],gap='large')
    with main:
        with st.container(border=True):
            ui.section('日常消费节奏','每天一点点，连成这个月的生活。')
            st.plotly_chart(ui.trend_chart(daily_trend(frame,month)),use_container_width=True,config={'displayModeBar':False})
    with aside:
        ui.budget_card(summary,plan)
    st.write('')
    main,aside=st.columns([1.85,1],gap='large')
    with main:
        with st.container(border=True):
            a,b=st.columns([3,1],vertical_alignment='center')
            with a: ui.section('最近的几笔','小小的记录，也能慢慢形成习惯。')
            with b: st.button('＋ 记一笔',type='primary',use_container_width=True,on_click=navigate,args=('记一笔',))
            ui.ledger_table(frame,limit=5)
    with aside:
        ui.section('预算小观察','提醒是线索，消费是否必要由你判断。')
        anomalies=detect_anomalies(frame)
        if not anomalies.empty:
            top=anomalies.iloc[0]
            ui.insight('有一笔消费值得回看',f"{top['category']} ¥{ui.money(top['amount'])}，高于同类消费的观察阈值。",True,'!')
        elif frame.empty:
            ui.insight('从第一笔开始','记录几笔日常消费，再来看看你的消费结构。',icon='＋')
        else:
            ui.insight('暂未发现明显异常','当前分类样本与规则下没有触发提醒；不代表每一笔都无需检查。',icon='✓')
        categories=category_stats(frame)
        if not categories.empty:
            top=categories.iloc[0]
            ui.insight(f"{top['category']}占支出 {top['share']:.0%}",'可以先关注支出最多的一类，再决定要不要调整。',icon='↗')
        if plan:
            ui.insight('给计划留一笔预留金',f"本月已预留 ¥{ui.money(plan.reserve,0)}，这部分不会计入日均可用金额。",icon='◷')
        else:
            st.button('设置本月预算',use_container_width=True,on_click=navigate,args=('预算管理',))


def entry(conn,month,today,navigate,is_demo):
    left,right=st.columns([1.6,1],gap='large')
    with left:
        words,manual=st.tabs(['一句话记账','手动填写'])
        with words:
            st.markdown('<div class="entry-example">试试：今天午饭 18 元 · 昨天地铁 6 元 · 兼职收入 300 元</div>',unsafe_allow_html=True)
            text=st.text_area('这一笔是什么？',placeholder='例如：昨天买教材 58 元',height=105,max_chars=300,key='entry_text')
            if st.button('解析这笔记录',type='primary',use_container_width=True):
                try:
                    st.session_state['_parsed_entry']=parse_entry(text,datetime.combine(today,datetime.now().time()))
                    st.session_state['_parsed_source']=text
                    st.session_state['_entry_generation']=st.session_state.get('_entry_generation',0)+1
                except ValidationError as exc:
                    st.session_state.pop('_parsed_entry',None)
                    st.error(str(exc))
            draft=st.session_state.get('_parsed_entry')
            if draft and st.session_state.get('_parsed_source')==text:
                st.markdown('<div class="preview-panel">已整理好这一笔。核对下方金额、日期和分类，确认后再保存。</div>',unsafe_allow_html=True)
                generation=st.session_state.get('_entry_generation',0)
                with st.form(f'confirm_entry_{generation}'):
                    a,b=st.columns(2)
                    with a:
                        amount=st.number_input('确认金额 / 元',min_value=.01,max_value=1000000.,value=float(draft['amount']),step=1.)
                        kind=st.selectbox('确认类型',['支出','收入'],index=0 if draft['t_type']=='expense' else 1)
                    with b:
                        category=st.selectbox('确认分类',CATEGORIES,index=CATEGORIES.index(draft['category']))
                        when=st.date_input('确认日期',value=draft['t_time'].date())
                    fixed=st.checkbox('这是固定支出',value=draft['is_fixed'])
                    note=st.text_input('备注',value=draft['note'],max_chars=500)
                    confirmed=st.form_submit_button('确认并保存',type='primary',use_container_width=True)
                if confirmed:
                    try:
                        storage.add_entry(conn,t_type='expense' if kind=='支出' else 'income',amount=amount,t_time=datetime.combine(when,draft['t_time'].time()),category=category,note=note,is_fixed=fixed)
                        st.session_state.pop('_parsed_entry',None)
                        st.session_state['_flash']='这一笔已保存。若日期不属于当前月份，可切换月份查看。'
                        st.rerun()
                    except ValidationError as exc:
                        st.error(str(exc))
            elif draft:
                st.info('输入内容已变更，请重新解析后再保存。')
        with manual:
            with st.form('manual_entry',clear_on_submit=True):
                a,b=st.columns(2)
                with a:
                    kind=st.selectbox('收支类型',['支出','收入'])
                    amount=st.number_input('金额 / 元',min_value=.01,max_value=1000000.,value=18.,step=1.)
                with b:
                    category=st.selectbox('消费分类',CATEGORIES)
                    when=st.date_input('记账日期',value=today)
                note=st.text_input('备注（选填）',max_chars=500,placeholder='给未来的自己留个小提示')
                fixed=st.checkbox('固定支出，例如房租或月度订阅')
                saved=st.form_submit_button('保存这笔记录',type='primary',use_container_width=True)
            if saved:
                try:
                    storage.add_entry(conn,t_type='expense' if kind=='支出' else 'income',amount=amount,t_time=datetime.combine(when,datetime.now().time()),category=category,note=note,is_fixed=fixed)
                    st.session_state['_flash']='记录已保存。'
                    st.rerun()
                except ValidationError as exc:
                    st.error(str(exc))
    with right:
        with st.container(border=True):
            ui.section('记账也可以很轻','不用把生活变成一张复杂的表。')
            ui.insight('一次一笔，更清楚','一句话里保留一个金额。多笔消费请分开记录。',icon='1')
            ui.insight('日期可以自己说','支持 YYYY-MM-DD，以及“今天、昨天、前天”。没有日期时记为今天。',icon='2')
            ui.insight('保存前，由你确认','解析使用本地规则，不调用大模型；你可以修改分类、日期和金额。',icon='3')
    st.write('')
    ui.section('最近记录','这里展示当前账本最近的 8 笔记录，不受上方月份筛选限制。')
    ui.ledger_table(as_frame(storage.list_entries(conn)),8)


def analytics(conn,month,today,navigate,is_demo):
    frame,plan,summary=context(conn,month,today)
    categories=category_stats(frame)
    if categories.empty:
        ui.empty('这个月还没有支出','先记下几笔消费，再来看看钱都花在哪里。')
        st.button('去记一笔',type='primary',on_click=navigate,args=('记一笔',))
        return
    left,right=st.columns([1.55,1],gap='large')
    with left:
        with st.container(border=True):
            ui.section('支出从哪里开始关注','柱形看金额，折线看累计占比。')
            fig=make_subplots(specs=[[{'secondary_y':True}]])
            fig.add_trace(go.Bar(x=categories['category'],y=categories['amount'],name='支出',marker_color=ui.COLORS[0],hovertemplate='%{x}<br>¥%{y:,.2f}<extra></extra>'),secondary_y=False)
            fig.add_trace(go.Scatter(x=categories['category'],y=categories['cumulative']*100,name='累计占比',mode='lines+markers',line=dict(color=ui.COLORS[1],width=2),hovertemplate='累计 %{y:.1f}%<extra></extra>'),secondary_y=True)
            ui.chart_style(fig,300)
            fig.update_yaxes(tickprefix='¥ ',secondary_y=False)
            fig.update_yaxes(range=[0,105],ticksuffix='%',showgrid=False,secondary_y=True)
            st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
    with right:
        with st.container(border=True):
            ui.section('消费结构','先看占比，再看是否符合自己的计划。')
            st.plotly_chart(ui.donut_chart(categories),use_container_width=True,config={'displayModeBar':False})
            for i,row in categories.head(4).iterrows():
                st.markdown(f'<div class="budget-detail"><span style="color:{ui.COLORS[i]}">● {escape(row["category"])}</span><strong>{row["share"]:.1%}</strong></div>',unsafe_allow_html=True)
    with st.container(border=True):
        ui.section('收支的月度节奏','覆盖所选月份的全部日期，没有记录的日期显示为 0。')
        st.plotly_chart(ui.trend_chart(daily_trend(frame,month),True),use_container_width=True,config={'displayModeBar':False})
    ui.section('值得回看的一笔','按所选月份、同类消费比较；每类至少需要 5 笔记录。')
    anomalies=detect_anomalies(frame)
    if anomalies.empty:
        ui.insight('当前没有触发提醒','可能是消费没有超过观察阈值，也可能是同类样本还不够。',icon='✓')
    else:
        for _,row in anomalies.iterrows():
            ui.insight(f"{row['category']} · ¥{ui.money(row['amount'])}",f"{row['t_time']:%m月%d日} · 同类 {int(row['sample_count'])} 笔，观察阈值 ¥{ui.money(row['threshold'])}。备注：{row['note'] or '无'}",True,'!')
    with st.expander('提醒的依据是什么？'):
        st.write('同一分类内，阈值为中位数 + 5 × MAD（绝对中位差）。MAD 为 0 时，使用中位数的 2.5 倍与“中位数 + 30 元”中较大的值。只有金额至少为 30 元且超过阈值时才提醒。样本少于 5 笔时暂不判断。')
        st.caption('提醒不能判断消费是否必要，也不代表欺诈、重复扣费或记账错误。')


def budget(conn,month,today,navigate,is_demo):
    frame,plan,summary=context(conn,month,today)
    left,right=st.columns([1.5,1],gap='large')
    with left:
        with st.form('budget_form'):
            ui.section('安排这个月的生活费','预算可以调整，给计划留一点弹性。')
            total=st.number_input('本月总预算 / 元',min_value=1.,max_value=1000000.,value=float(plan.total) if plan else 3000.,step=100.)
            a,b=st.columns(2)
            with a: fixed=st.number_input('固定支出预算 / 元',min_value=0.,max_value=1000000.,value=float(plan.fixed) if plan else 600.,step=50.,help='预计会发生的房租、订阅等固定开销。')
            with b: reserve=st.number_input('预留金 / 元',min_value=0.,max_value=1000000.,value=float(plan.reserve) if plan else 300.,step=50.,help='暂时不安排使用的金额，不计入每日可用额度。')
            saved=st.form_submit_button('保存预算安排',type='primary',use_container_width=True)
        if saved:
            try:
                storage.save_budget(conn,Budget(month,total,fixed,reserve))
                st.session_state['_flash']='本月预算已更新。'
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
        ui.insight('预算需要留在同一个范围里','固定支出预算与预留金之和，应当小于或等于总预算。',icon='i')
    with right:
        ui.budget_card(summary,plan)
    with st.expander('每日可用金额怎么算？'):
        st.write('先从总预算中减去已发生的支出，再减去预留金，以及尚未发生的固定支出预算，最后除以剩余天数（包含今天）。可用金额最低为 0。')
        st.write('历史月份显示为已结算，不再给出每日可用值；未来月份按该月完整天数计算。预算不是预测，未记入账本的支出不会自动计入。')


def safe_export(frame):
    out=frame.copy()
    out['日期']=out['t_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    out['类型']=out['t_type'].map({'income':'收入','expense':'支出'})
    out['分类']=out['category']
    out['金额']=out['amount']
    out['备注']=out['note'].fillna('').map(lambda x:"'"+x if str(x).startswith(('=','+','-','@','\t','\r')) else x)
    out['固定支出']=out['is_fixed'].map({0:'否',1:'是'})
    return out[['日期','类型','分类','金额','备注','固定支出']].to_csv(index=False).encode('utf-8-sig')


def ledger(conn,month,today,navigate,is_demo):
    all_months=st.checkbox('查看全部月份',key='all_months')
    frame=as_frame(storage.list_entries(conn,None if all_months else month))
    a,b=st.columns([3,1],vertical_alignment='center')
    with a: ui.section('收支明细',f'共 {len(frame)} 笔记录 · '+('全部月份' if all_months else month))
    with b:
        if not frame.empty:
            st.download_button('↓ 导出 CSV',safe_export(frame),file_name=f'CampusBudget_{"all" if all_months else month}.csv',mime='text/csv',use_container_width=True)
    kind=st.selectbox('筛选类型',['全部','支出','收入'])
    filtered=frame if kind=='全部' else frame[frame['t_type']==('expense' if kind=='支出' else 'income')]
    ui.ledger_table(filtered)
    st.caption('导出范围为当前月份或全部月份，不受“筛选类型”影响。文件可用 Excel 打开。')
    if not frame.empty:
        with st.expander('删除一笔记录'):
            lookup={int(row['id']):f"{row['t_time']:%Y-%m-%d} · {row['category']} · ¥{row['amount']:.2f} · {row['note'] or '无备注'}" for _,row in frame.iterrows()}
            selected=st.selectbox('选择记录',list(lookup),format_func=lambda k:lookup[k])
            confirmed=st.checkbox('我确认删除这笔记录',key='confirm_delete')
            if st.button('删除所选记录',disabled=not confirmed):
                storage.delete_entry(conn,selected)
                st.session_state['_flash']='所选记录已删除。'
                st.rerun()
    st.write('')
    ui.insight('数据属于你','演示账本仅保留在当前浏览器会话对应的内存里；本地账本保存在当前电脑的数据文件中。建议定期导出备份。',icon='↙')
