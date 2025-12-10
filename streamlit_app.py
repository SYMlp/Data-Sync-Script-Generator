import streamlit as st
from typing import List, Dict, Any
import time
import json
import os
import sys

# 导入后端模块
from src.core import DatabaseConnector, MetaDataQuerier
from src.services import ConfigService
from src.generator import SqlGenerator
from src.ui.import_helper import render_import_helper_tab

# --- 配置文件管理 ---
PROFILE_FILE = "connection_profiles.json"

def get_app_dir():
    """获取应用程序运行目录 (兼容 .exe 和 .py)"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe 运行
        return os.path.dirname(sys.executable)
    else:
        # 如果是脚本运行
        return os.path.dirname(os.path.abspath(__file__))

def load_last_profile():
    """加载最后一次使用的配置"""
    try:
        file_path = os.path.join(get_app_dir(), PROFILE_FILE)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"无法加载配置文件: {e}")
    return {}

def save_current_profile(profile_data: Dict[str, Any]):
    """保存当前配置"""
    try:
        file_path = os.path.join(get_app_dir(), PROFILE_FILE)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"无法保存配置文件: {e}")

# --- 页面配置 ---
st.set_page_config(
    page_title="MySQL 同步脚本生成器",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 状态管理 (State Management) ---
def init_session_state():
    """统一初始化 Session State"""
    defaults = {
        'source_db': None,
        'target_db': None,
        'source_querier': None,
        'target_querier': None,
        'config_service': None,
        'table_list': [],
        'is_connected': False,
        'conn_info': {},
        'has_loaded_profile': False,
        'filter_rules': [{'field': '', 'op': '=', 'val': ''}],
        'connect_error': None
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # 加载本地配置到 session_state (仅一次)
    if not st.session_state.has_loaded_profile:
        last_profile = load_last_profile()
        if last_profile:
            # 将文件中的配置注入到 session_state 中
            for key, val in last_profile.items():
                # 只注入连接相关的 key
                if key in ['src_host', 'src_port', 'src_user', 'src_pass', 'src_db',
                           'tgt_host', 'tgt_port', 'tgt_user', 'tgt_pass', 'tgt_db']:
                    st.session_state[key] = val
        st.session_state.has_loaded_profile = True

# 执行初始化
init_session_state()

# --- 辅助函数 ---
def format_column_option(col: Dict[str, Any]) -> str:
    """格式化字段选项显示: [PK] field_name - comment"""
    name = col['字段名']
    comment = col.get('字段注释', '').strip()
    key_type = col.get('键类型', '')
    
    tags = []
    if key_type == 'PRI':
        tags.append("🔑PK")
    elif key_type == 'UNI':
        tags.append("🌟Unique")
    elif key_type == 'MUL':
        tags.append("🔗Index")
        
    tag_str = f"[{'|'.join(tags)}] " if tags else ""
    comment_str = f" - {comment}" if comment else ""
    
    return f"{tag_str}{name}{comment_str}"

def find_default_index(columns: List[Dict[str, Any]], criteria_type: str) -> int:
    """根据条件查找默认选中的字段索引"""
    if not columns:
        return 0
        
    for idx, col in enumerate(columns):
        key_type = col.get('键类型', '')
        name = col['字段名'].lower()
        
        if criteria_type == 'primary_unique':
            # 优先找主键或唯一键
            if key_type in ('PRI', 'UNI'):
                return idx
        elif criteria_type == 'foreign_key':
            # 优先找外键 (通常是 MUL 或者名字包含 id)
            if key_type == 'MUL' or (name.endswith('id') and key_type != 'PRI'):
                return idx
                
    return 0

def get_default_exclude_fields(columns: List[Dict[str, Any]]) -> List[str]:
    """根据表结构获取建议排除的字段（如创建时间、更新人等）"""
    common_excludes = {
        'create_time', 'create_user', 'create_by', 'created_at', 'created_by',
        'update_time', 'update_user', 'update_by', 'updated_at', 'updated_by',
        'modify_time', 'modify_user', 'is_deleted', 'is_del', 'del_flag'
    }
    
    found_fields = []
    for col in columns:
        if col['字段名'].lower() in common_excludes:
            found_fields.append(col['字段名'])
    return found_fields

def get_smart_filter_rule(columns: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """智能识别删除标记字段并生成过滤规则"""
    del_flags = {'is_del', 'is_deleted', 'del_flag', 'delete_flag', 'is_active'}
    
    for col in columns:
        name = col['字段名'].lower()
        if name in del_flags:
            # 针对 is_active 特殊处理，通常 active=1 是有效
            if name == 'is_active':
                return [{'field': col['字段名'], 'op': '=', 'val': '1'}]
            else:
                return [{'field': col['字段名'], 'op': '=', 'val': '0'}]
    
    # 默认空规则
    return [{'field': '', 'op': '=', 'val': ''}]

def build_single_rule_sql(field: str, op: str, val: str) -> str:
    """构建单条规则的 SQL 片段"""
    if not field or not op:
        return ""
        
    final_val = val.strip()
    
    # 智能处理引号：如果用户已经手动加了引号（单/双），则保留原样；否则自动加单引号
    # 但排除数字类型
    if op not in ('IS NULL', 'IS NOT NULL'):
        is_quoted = (final_val.startswith("'") and final_val.endswith("'")) or \
                    (final_val.startswith('"') and final_val.endswith('"'))
                    
        if final_val and not final_val.isdigit() and not is_quoted:
             final_val = f"'{final_val}'"
        elif not final_val:
            return ""
            
    if op in ('IS NULL', 'IS NOT NULL'):
        return f"{field} {op}"
    else:
        return f"{field} {op} {final_val}"

def find_smart_target_table_index(target_tables: List[str], source_table_name: str) -> int:
    """
    智能寻找目标表索引
    策略:
    1. 优先找 suffix 匹配: table_name + _dest / _bak / _sync
    2. 其次找完全同名: table_name (如果源/目标库不同)
    3. 默认返回 0
    """
    if not target_tables:
        return 0
        
    suffixes = ['_dest', '_bak', '_sync', '_target']
    
    # 1. 尝试匹配后缀
    for suffix in suffixes:
        candidate = f"{source_table_name}{suffix}"
        if candidate in target_tables:
            return target_tables.index(candidate)
            
    # 2. 尝试完全同名
    if source_table_name in target_tables:
        return target_tables.index(source_table_name)
        
    return 0

def check_suicide_risk(src_table: str, tgt_table: str) -> bool:
    """检测是否是同一数据库的同一张表 (自杀式操作)"""
    conn_info = st.session_state.get('conn_info', {})
    
    # 如果连接信息不完整，跳过检查（但理论上连接了就有）
    if not conn_info.get('src_host') or not conn_info.get('tgt_host'):
        return False
        
    # 比较连接参数
    is_same_host = (conn_info['src_host'] == conn_info['tgt_host'])
    is_same_port = (conn_info['src_port'] == conn_info['tgt_port'])
    is_same_db = (conn_info['src_db'] == conn_info['tgt_db'])
    
    if is_same_host and is_same_port and is_same_db:
        if src_table == tgt_table:
            return True
            
    return False

# --- Callbacks (联动逻辑) ---

def on_src_main_change():
    """当源主表改变时触发"""
    new_src_table = st.session_state.src_main
    if not new_src_table:
        return

    if 'tgt_main' not in st.session_state:
        st.session_state.tgt_main = ""
    if 'tgt_child' not in st.session_state:
        st.session_state.tgt_child = ""

    # 2. 联动目标表 (仅在下拉模式下自动匹配)
    use_manual = st.session_state.get('use_manual_target', False)
    if not use_manual and st.session_state.target_querier:
        tgt_opts = st.session_state.target_querier.get_all_tables() or []
        idx = find_smart_target_table_index(tgt_opts, new_src_table)
        if tgt_opts:
            # 更新 session_state 触发 selectbox 更新
            st.session_state.tgt_main_select = tgt_opts[idx]
            st.session_state.tgt_main = tgt_opts[idx]
    elif use_manual:
        # 如果是手动模式，尝试简单的后缀匹配填入文本框
        st.session_state.tgt_main_input = f"{new_src_table}_dest"
        st.session_state.tgt_main = f"{new_src_table}_dest"

    # 3. 联动过滤规则 (重置为默认推荐)
    if st.session_state.source_querier:
        cols = st.session_state.source_querier.get_table_columns(new_src_table) or []
        st.session_state.filter_rules = get_smart_filter_rule(cols)

def on_src_child_change():
    """当源从表改变时触发"""
    new_src_child = st.session_state.src_child
    if not new_src_child:
        return
        
    if 'tgt_child' not in st.session_state:
        st.session_state.tgt_child = ""

    # 1. 联动目标从表
    use_manual = st.session_state.get('use_manual_target', False)
    if not use_manual and st.session_state.target_querier:
        tgt_opts = st.session_state.target_querier.get_all_tables() or []
        idx = find_smart_target_table_index(tgt_opts, new_src_child)
        if tgt_opts:
            st.session_state.tgt_child_select = tgt_opts[idx]
            st.session_state.tgt_child = tgt_opts[idx]
    elif use_manual:
        st.session_state.tgt_child_input = f"{new_src_child}_dest"
        st.session_state.tgt_child = f"{new_src_child}_dest"

def handle_connect():
    """连接按钮回调：执行连接并更新状态"""
    # 1. 收集连接信息 (直接从 session_state 获取，因为 Text Input 绑定了 key)
    conn_info = {
        'src_host': st.session_state.get('src_host'), 
        'src_port': st.session_state.get('src_port'), 
        'src_user': st.session_state.get('src_user'), 
        'src_pass': st.session_state.get('src_pass'), 
        'src_db': st.session_state.get('src_db'),
        'tgt_host': st.session_state.get('tgt_host'), 
        'tgt_port': st.session_state.get('tgt_port'), 
        'tgt_user': st.session_state.get('tgt_user'), 
        'tgt_pass': st.session_state.get('tgt_pass'), 
        'tgt_db': st.session_state.get('tgt_db')
    }
    st.session_state.conn_info = conn_info

    # 2. 执行连接
    is_success = connect_databases(
        src_config={'host': conn_info['src_host'], 'port': conn_info['src_port'], 
                   'user': conn_info['src_user'], 'password': conn_info['src_pass'], 
                   'database': conn_info['src_db']},
        tgt_config={'host': conn_info['tgt_host'], 'port': conn_info['tgt_port'], 
                   'user': conn_info['tgt_user'], 'password': conn_info['tgt_pass'], 
                   'database': conn_info['tgt_db']}
    )

    # 3. 后续处理
    if is_success:
        save_current_profile(conn_info)
        st.toast("✅ 数据库连接成功！")
    else:
        # 错误信息已经在 connect_databases 中写入 session_state.connect_error
        st.toast("❌ 连接失败，请检查配置", icon="🚨")

def add_filter_rule():
    """添加一条新的过滤规则"""
    st.session_state.filter_rules.append({'field': '', 'op': '=', 'val': ''})

def remove_filter_rule(index: int):
    """删除指定索引的过滤规则"""
    if 0 <= index < len(st.session_state.filter_rules):
        del st.session_state.filter_rules[index]

# --- 侧边栏：连接配置 (Sidebar) ---
def render_sidebar():
    with st.sidebar:
        st.header("🔌 数据库连接")
        
        st.subheader("源数据库 (Source)")
        # 使用 session_state.get 获取默认值，如果没有则回退到硬编码默认值
        st.text_input("Host", value=st.session_state.get('src_host', "127.0.0.1"), key="src_host")
        st.number_input("Port", value=int(st.session_state.get('src_port', 3310)), step=1, key="src_port")
        st.text_input("Username", value=st.session_state.get('src_user', "root"), key="src_user")
        st.text_input("Password", value=st.session_state.get('src_pass', "123456"), type="password", key="src_pass")
        st.text_input("Database", value=st.session_state.get('src_db', "test"), key="src_db")

        st.divider()

        st.subheader("目标数据库 (Target)")
        st.text_input("Host", value=st.session_state.get('tgt_host', "127.0.0.1"), key="tgt_host")
        st.number_input("Port", value=int(st.session_state.get('tgt_port', 3310)), step=1, key="tgt_port")
        st.text_input("Username", value=st.session_state.get('tgt_user', "root"), key="tgt_user")
        st.text_input("Password", value=st.session_state.get('tgt_pass', "123456"), type="password", key="tgt_pass")
        st.text_input("Database", value=st.session_state.get('tgt_db', "test"), key="tgt_db")

        st.divider()

        if st.button("连接数据库", type="primary", use_container_width=True, on_click=handle_connect):
            pass
        
        if st.session_state.is_connected:
            # 显示当前连接的数据库名
            s_db = st.session_state.conn_info.get('src_db', 'Unknown')
            t_db = st.session_state.conn_info.get('tgt_db', 'Unknown')
            st.success(f"✅ 已连接: {s_db} -> {t_db}")
        elif st.session_state.get('connect_error'):
            st.error(f"❌ 连接失败: {st.session_state.connect_error}")

def connect_databases(src_config: Dict, tgt_config: Dict) -> bool:
    """
    连接数据库并初始化服务
    Returns:
        bool: 连接是否成功
    """
    try:
        # 清理旧连接
        if st.session_state.source_db:
            st.session_state.source_db.disconnect()
        if st.session_state.target_db:
            st.session_state.target_db.disconnect()

        # 必须提供数据库名称
        if not src_config['database'] or not tgt_config['database']:
            st.session_state.connect_error = "必须填写数据库名称"
            st.session_state.is_connected = False
            return False

        with st.spinner("正在连接数据库..."):
            # 初始化连接器
            source_db = DatabaseConnector(src_config)
            target_db = DatabaseConnector(tgt_config)

            # 尝试连接
            if source_db.connect() and target_db.connect():
                st.session_state.source_db = source_db
                st.session_state.target_db = target_db
                
                # 初始化查询器和服务
                source_querier = MetaDataQuerier(source_db)
                target_querier = MetaDataQuerier(target_db)
                
                st.session_state.source_querier = source_querier
                st.session_state.target_querier = target_querier
                st.session_state.config_service = ConfigService(source_querier, target_querier)
                
                # 获取表列表缓存
                st.session_state.table_list = source_querier.get_all_tables() or []
                
                st.session_state.is_connected = True
                st.session_state.connect_error = None
                return True
            else:
                st.session_state.is_connected = False
                st.session_state.connect_error = "无法连接到源或目标数据库，请检查配置。"
                return False
                
    except Exception as e:
        st.session_state.is_connected = False
        st.session_state.connect_error = str(e)
        return False

# --- 组件渲染函数 (Component Rendering) ---

def on_tgt_main_select_change():
    """目标主表下拉框变化"""
    st.session_state.tgt_main = st.session_state.tgt_main_select

def on_tgt_child_select_change():
    """目标从表下拉框变化"""
    st.session_state.tgt_child = st.session_state.tgt_child_select

def on_tgt_main_input_change():
    """目标主表输入框变化"""
    st.session_state.tgt_main = st.session_state.tgt_main_input

def on_tgt_child_input_change():
    """目标从表输入框变化"""
    st.session_state.tgt_child = st.session_state.tgt_child_input

def render_table_section():
    """渲染表结构配置区域"""
    st.header("1. 表结构配置")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("源数据库 (Source)")
        src_main = st.selectbox("源主表", options=st.session_state.table_list, key="src_main", on_change=on_src_main_change)
        src_child = st.selectbox("源从表", options=st.session_state.table_list, key="src_child", on_change=on_src_child_change)
    
    with col2:
        st.subheader("目标数据库 (Target)")
        
        # 添加手动输入切换开关
        use_manual = st.checkbox("手动输入表名 (目标表不存在时使用)", key="use_manual_target")
        
        tgt_table_list = st.session_state.target_querier.get_all_tables() or []
        
        if use_manual:
            # 手动模式：使用 text_input
            tgt_main = st.text_input(
                "目标主表", 
                value=st.session_state.get('tgt_main', ''), 
                key="tgt_main_input",
                on_change=on_tgt_main_input_change
            )
            tgt_child = st.text_input(
                "目标从表", 
                value=st.session_state.get('tgt_child', ''), 
                key="tgt_child_input",
                on_change=on_tgt_child_input_change
            )
        else:
            # 下拉模式：使用 selectbox
            # 需要处理当前值可能不在列表中的情况
            current_tgt_main = st.session_state.get('tgt_main', '')
            current_tgt_child = st.session_state.get('tgt_child', '')
            
            idx_main = 0
            if current_tgt_main in tgt_table_list:
                idx_main = tgt_table_list.index(current_tgt_main)
                
            idx_child = 0
            if current_tgt_child in tgt_table_list:
                idx_child = tgt_table_list.index(current_tgt_child)

            # 注意：这里 key 使用 _select 后缀，与 input 分离
            tgt_main = st.selectbox(
                "目标主表", 
                options=tgt_table_list, 
                index=idx_main, 
                key="tgt_main_select",
                on_change=on_tgt_main_select_change
            )
            tgt_child = st.selectbox(
                "目标从表", 
                options=tgt_table_list, 
                index=idx_child, 
                key="tgt_child_select",
                on_change=on_tgt_child_select_change
            )
            
            # 同步回主状态 (用于首次渲染或切换时保持一致)
            st.session_state.tgt_main = tgt_main
            st.session_state.tgt_child = tgt_child

    # 实时自杀风险检测
    risk_main = check_suicide_risk(src_main, tgt_main)
    risk_child = check_suicide_risk(src_child, tgt_child)
    
    if risk_main:
        st.error(f"❌ 危险配置：主表 '{src_main}' 源与目标完全相同！这将导致数据被清空。")
    if risk_child:
        st.error(f"❌ 危险配置：从表 '{src_child}' 源与目标完全相同！这将导致数据被清空。")

    return src_main, src_child, tgt_main, tgt_child, (risk_main or risk_child)

def render_relation_section(src_main, src_child, src_main_cols, src_child_cols):
    """渲染关联关系配置区域"""
    st.header("2. 关联关系配置")
    
    # 图解说明
    with st.container():
        st.caption("📖 主从表关系示意图")
        st.graphviz_chart(f"""
            digraph G {{
                rankdir=LR;
                bgcolor="transparent";
                node [shape=box, style="filled,rounded", fontname="Sans-Serif", margin=0.2];
                edge [fontname="Sans-Serif", fontsize=10, color="#666666"];
                
                Main [label=<{src_main}<BR/><FONT POINT-SIZE="10">主表 (Parent)</FONT>>, fillcolor="#e8f5e9", color="#2e7d32", fontcolor="#1b5e20"];
                Child [label=<{src_child}<BR/><FONT POINT-SIZE="10">从表 (Child)</FONT>>, fillcolor="#e3f2fd", color="#1565c0", fontcolor="#0d47a1"];
                
                Main -> Child [label="1 对 多\\n(Foreign Key)", penwidth=1.5, arrowsize=0.8];
            }}
        """, use_container_width=True)

    st.markdown("---")

    # 关联键配置
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("##### 🗝️ 主表唯一标识 (Main Unique Key)")
        st.caption("用于 **定位** 和 **遍历** 记录。生成器将基于此字段开启游标循环。推荐使用业务唯一键（如订单号）。")
        
        default_idx_main = find_default_index(src_main_cols, 'primary_unique')
        main_unique_col = st.selectbox(
            "选择主表字段",
            options=src_main_cols,
            index=default_idx_main,
            format_func=format_column_option,
            key=f"main_unique_key_select_{src_main}" 
        )
        main_unique_key = main_unique_col['字段名'] if main_unique_col else ""
        
        if main_unique_col and 'PRI' in main_unique_col.get('键类型', ''):
            st.info("ℹ️ 您当前使用了主键。如果源库和目标库ID不一致（如自增ID不同步），建议改用业务唯一键。")

    with c2:
        st.markdown("##### 🔗 主从关联外键 (Foreign Key)")
        st.caption("从表中用于 **指向主表** 的字段。生成器用它来查找从表记录。")
        
        default_idx_fk = find_default_index(src_child_cols, 'foreign_key')
        fk_col = st.selectbox(
            "选择从表字段",
            options=src_child_cols,
            index=default_idx_fk,
            format_func=format_column_option,
            key=f"fk_key_select_{src_child}"
        )
        fk_key = fk_col['字段名'] if fk_col else ""

    with c3:
        st.markdown("##### 🆔 从表记录唯一标识 (Child Record Key)")
        st.caption("用于 **区分** 同一主表下的多条从表记录。用于判断记录是更新还是插入。")
        
        default_idx_child = find_default_index(src_child_cols, 'primary_unique')
        child_unique_col = st.selectbox(
            "选择从表字段",
            options=src_child_cols,
            index=default_idx_child,
            format_func=format_column_option,
            key=f"child_unique_key_select_{src_child}"
        )
        child_unique_key = child_unique_col['字段名'] if child_unique_col else ""

    st.divider()
    return main_unique_key, fk_key, child_unique_key

def render_filter_section(src_main_cols, src_child_cols, src_main_name, src_child_name):
    """渲染高级规则与过滤区域"""
    with st.expander("⚙️ 高级同步规则与过滤", expanded=True):
        st.markdown("#### 1. 过滤条件 (Filter)")
        
        use_visual_builder = st.checkbox("使用可视化构建器 (Visual Builder)", value=True)
        
        final_filter_sql = ""
        
        if use_visual_builder:
            # 动态渲染规则行
            generated_sqls = []
            
            for i, rule in enumerate(st.session_state.filter_rules):
                fc1, fc2, fc3, fc4 = st.columns([2, 1, 2, 0.5])
                with fc1:
                    # 字段选择
                    col_names = [c['字段名'] for c in src_main_cols]
                    
                    if rule['field'] not in col_names:
                         curr_idx = 0
                         if col_names:
                             rule['field'] = col_names[0]
                    else:
                         curr_idx = col_names.index(rule['field'])
                    
                    sel_col = st.selectbox(
                        f"字段 #{i+1}", 
                        options=src_main_cols, 
                        index=curr_idx,
                        format_func=format_column_option, 
                        key=f"rule_field_{i}",
                        label_visibility="collapsed"
                    )
                    rule['field'] = sel_col['字段名'] if sel_col else ""

                with fc2:
                    op_opts = ["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "IS NULL", "IS NOT NULL"]
                    curr_op_idx = op_opts.index(rule['op']) if rule['op'] in op_opts else 0
                    rule['op'] = st.selectbox(
                        f"Op #{i+1}", 
                        options=op_opts, 
                        index=curr_op_idx,
                        key=f"rule_op_{i}",
                        label_visibility="collapsed"
                    )

                with fc3:
                    placeholder_text = "值 (自动处理引号)"
                    if rule['op'] == 'LIKE':
                        placeholder_text = "例如: %南向% (无需引号)"
                        
                    rule['val'] = st.text_input(
                        f"Val #{i+1}", 
                        value=rule['val'],
                        disabled=(rule['op'] in ('IS NULL', 'IS NOT NULL')), 
                        key=f"rule_val_{i}",
                        label_visibility="collapsed",
                        placeholder=placeholder_text
                    )

                with fc4:
                    st.button("🗑️", key=f"del_rule_{i}", on_click=remove_filter_rule, args=(i,), help="删除此规则")

                # 生成单条 SQL
                sql_part = build_single_rule_sql(rule['field'], rule['op'], rule['val'])
                if sql_part:
                    generated_sqls.append(sql_part)
            
            st.button("➕ 添加规则", on_click=add_filter_rule)
                
            final_filter_sql = " AND ".join(generated_sqls)
            
        # 双向同步展示区
        st.markdown("##### 预览与微调 (Preview & Edit)")
        filter_condition = st.text_area(
            "生成的 SQL WHERE 子句 (可直接修改)", 
            value=final_filter_sql if use_visual_builder else "is_del = 0",
            help="这里展示最终用于生成的 SQL 条件，您可以在此手动修正。",
            height=100
        )

        st.divider()
        
        st.markdown("#### 2. 排除字段 (Exclude Fields)")
        st.caption("选择不需要同步的字段 (如审计字段)")
        
        ec1, ec2 = st.columns(2)
        with ec1:
            default_excludes_main = get_default_exclude_fields(src_main_cols)
            exclude_main_selection = st.multiselect(
                "主表排除字段", 
                options=[col['字段名'] for col in src_main_cols],
                default=default_excludes_main,
                key=f"exclude_main_multi_{src_main_name}"
            )
            
        with ec2:
            default_excludes_child = get_default_exclude_fields(src_child_cols)
            exclude_child_selection = st.multiselect(
                "从表排除字段", 
                options=[col['字段名'] for col in src_child_cols],
                default=default_excludes_child,
                key=f"exclude_child_multi_{src_child_name}"
            )

    st.divider()
    return filter_condition, exclude_main_selection, exclude_child_selection

# --- 主工作区 (Main Area) ---
def render_main_area():
    st.title("🛠️ MySQL 同步脚本生成器")

    if not st.session_state.is_connected:
        st.info("👈 请先在左侧侧边栏配置并连接数据库。")
        return

    # 1. 导航栏 (解决上传文件后 Tab 重置问题)
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = "MySQL 脚本生成器"

    # 使用 radio 模拟 tabs，状态完全可控
    tab_selection = st.radio(
        "",
        ["MySQL 脚本生成器", "批量用户导入助手"],
        horizontal=True,
        key="current_tab", # 自动双向绑定
        label_visibility="collapsed"
    )

    if tab_selection == "MySQL 脚本生成器":
        render_generator_tab()
    else:
        render_import_helper_tab()

def render_generator_tab():
    # 1. 表结构配置
    src_main, src_child, tgt_main, tgt_child, is_risk = render_table_section()

    # 获取表字段元数据
    src_main_cols = st.session_state.source_querier.get_table_columns(src_main) or []
    src_child_cols = st.session_state.source_querier.get_table_columns(src_child) or []

    # 2. 关联关系配置
    main_unique_key, fk_key, child_unique_key = render_relation_section(
        src_main, src_child, src_main_cols, src_child_cols
    )

    # 3. 高级规则配置
    filter_condition, exclude_main_selection, exclude_child_selection = render_filter_section(
        src_main_cols, src_child_cols, src_main, src_child
    )

    # 4. 生成操作
    if st.button("🚀 生成同步脚本", type="primary", use_container_width=True, disabled=is_risk):
        if is_risk:
            st.error("🚫 已阻止生成：请先修改目标表配置，避免覆盖源数据。")
        else:
            generate_script(
                src_main, src_child, tgt_main, tgt_child,
                main_unique_key, fk_key, child_unique_key,
                filter_condition, exclude_main_selection, exclude_child_selection
            )

def generate_script(src_main, src_child, tgt_main, tgt_child, 
                   main_unique_key, fk_key, child_unique_key,
                   filter_condition, exclude_main_list, exclude_child_list):
    """执行脚本生成逻辑"""
    
    # 基础校验
    if not all([src_main, src_child, tgt_main, tgt_child, main_unique_key, fk_key, child_unique_key]):
        st.error("⚠️ 请填写所有必填字段（表名及所有关键键名）")
        return

    try:
        with st.spinner("正在分析表结构并生成脚本..."):
            # 1. 配置 ConfigService
            config_service = st.session_state.config_service
            
            config_service.configure_table_relations(
                source_main=src_main, source_child=src_child,
                target_main=tgt_main, target_child=tgt_child
            )
            
            config_service.configure_sync_keys(
                main_table_unique_key=main_unique_key,
                master_child_foreign_key=fk_key,
                child_table_unique_key=child_unique_key
            )
            
            config_service.configure_scope(
                source_filter_condition=filter_condition,
                exclude_fields_main=exclude_main_list,
                exclude_fields_child=exclude_child_list
            )
            
            # 2. 获取配置并生成
            final_config = config_service.get_current_config()
            generator = SqlGenerator(final_config, st.session_state.source_querier, st.session_state.target_querier)
            
            result_script = generator.generate_script()
            
            # 3. 展示结果
            st.success("🎉 脚本生成成功！")
            
            # 4. 获取完整脚本供下载和预览
            full_content = generator.generate_full_executable_script()
            
            st.subheader("生成的完整脚本 (Preview)")
            st.code(full_content, language='sql')
            
            st.download_button(
                label="📥 下载完整 SQL 脚本 (含定义、执行与清理)",
                data=full_content,
                file_name=f"sync_script_{int(time.time())}.sql",
                mime="application/sql"
            )
            
    except Exception as e:
        st.error(f"❌ 生成失败: {str(e)}")
        st.exception(e)

# --- 程序入口 ---
if __name__ == "__main__":
    render_sidebar()
    render_main_area()
