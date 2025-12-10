import streamlit as st
import pandas as pd
import requests
import json
import time
from typing import List, Dict, Any

def render_import_helper_tab():
    st.header("📊 批量用户导入助手")
    st.markdown("通过 Excel 上传用户数据，并生成 SQL 插入语句或批量调用 API。")

    # 1. 源数据准备 (Excel)
    st.subheader("1. 上传源数据 (Excel)")
    uploaded_file = st.file_uploader("上传用户 Excel 文件", type=['xlsx', 'xls'])
    
    if uploaded_file:
        try:
            # 读取 Excel
            df = pd.read_excel(uploaded_file)
            st.session_state['import_df'] = df
            
            # 展示预览
            st.success(f"✅ 成功加载 {len(df)} 条数据")
            with st.expander("数据预览 (前 5 行)", expanded=True):
                st.dataframe(df.head())
                
            # 获取 Excel 列头
            excel_columns = df.columns.tolist()
            
        except Exception as e:
            st.error(f"❌ 读取 Excel 失败: {e}")
            return
    else:
        st.info("请先上传 Excel 文件以开始。")
        return

    st.divider()

    # 2. 目标数据分析 (DB)
    st.subheader("2. 目标表配置")
    
    # 复用 session_state 中的 target_querier
    if 'target_querier' not in st.session_state or not st.session_state.target_querier:
        st.warning("⚠️ 请先在左侧连接数据库。")
        return

    target_querier = st.session_state.target_querier
    
    # 支持手动刷新表列表
    col_sel, col_btn = st.columns([4, 1])
    with col_sel:
        all_tables = st.session_state.get('table_list', [])
        # 如果缓存为空，尝试获取一次
        if not all_tables:
            all_tables = target_querier.get_all_tables() or []
            st.session_state.table_list = all_tables
            
        target_table = st.selectbox("选择目标用户表", options=all_tables, key="import_target_table")
        
    with col_btn:
        # 对齐按钮
        st.write("")
        st.write("")
        if st.button("🔄 刷新表", help="重新从数据库获取表列表"):
            with st.spinner("刷新中..."):
                updated_tables = target_querier.get_all_tables()
                st.session_state.table_list = updated_tables or []
                st.toast("表列表已更新", icon="✅")
                # 强制重新运行以更新下拉框
                st.rerun()

    if target_table:
        # 获取目标表字段
        db_columns = target_querier.get_table_columns(target_table) or []
        st.write(f"目标表 `{target_table}` 共有 {len(db_columns)} 个字段。")
        
        # 3. 字段映射
        st.subheader("3. 字段映射配置")
        st.caption("请为目标数据库字段选择对应的 Excel 列。留空表示不导入该字段。")
        
        mapping = {}
        
        # 使用两列布局
        col1, col2 = st.columns(2)
        
        # 将字段分两列显示
        mid_idx = (len(db_columns) + 1) // 2
        
        with col1:
            for col in db_columns[:mid_idx]:
                excel_col = render_mapping_field(col, excel_columns)
                if excel_col:
                    mapping[col['字段名']] = excel_col

        with col2:
            for col in db_columns[mid_idx:]:
                excel_col = render_mapping_field(col, excel_columns)
                if excel_col:
                    mapping[col['字段名']] = excel_col

        st.session_state['import_mapping'] = mapping
        
        st.divider()

        # 4. 执行与输出
        st.subheader("4. 执行导入")
        
        mode = st.radio("选择导入模式", ["生成 SQL 语句", "API 批量调用"], horizontal=True)
        
        if mode == "生成 SQL 语句":
            render_sql_generation_mode(df, target_table, mapping)
        else:
            render_api_mode(df, mapping)

def render_mapping_field(db_col: Dict[str, Any], excel_cols: List[str]) -> str:
    """渲染单个字段的映射组件"""
    col_name = db_col['字段名']
    col_comment = db_col.get('字段注释', '')
    col_type = db_col.get('类型', '')
    
    # 尝试自动匹配 (大小写不敏感)
    default_idx = 0
    for i, excel_col in enumerate(excel_cols):
        if excel_col.lower() == col_name.lower() or excel_col == col_comment:
            default_idx = i + 1 # +1 因为第一个是 None
            break
            
    options = ["(跳过)"] + excel_cols
    
    label = f"{col_name}"
    if col_comment:
        label += f" ({col_comment})"
    
    selected = st.selectbox(
        label,
        options=options,
        index=default_idx,
        key=f"map_{col_name}",
        help=f"类型: {col_type}"
    )
    
    return selected if selected != "(跳过)" else None

def render_sql_generation_mode(df: pd.DataFrame, table_name: str, mapping: Dict[str, str]):
    """SQL 生成模式"""
    if st.button("🚀 生成 INSERT SQL"):
        if not mapping:
            st.error("请至少映射一个字段！")
            return
            
        sqls = []
        columns = list(mapping.keys())
        cols_str = ", ".join([f"`{c}`" for c in columns])
        
        for _, row in df.iterrows():
            values = []
            for db_col in columns:
                excel_col = mapping[db_col]
                val = row.get(excel_col)
                
                # 简单的数据处理
                if pd.isna(val):
                    values.append("NULL")
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                else:
                    # 转义单引号
                    val_str = str(val).replace("'", "''")
                    values.append(f"'{val_str}'")
            
            vals_str = ", ".join(values)
            sqls.append(f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({vals_str});")
            
        final_sql = "\n".join(sqls)
        st.code(final_sql, language="sql")
        
        st.download_button(
            "📥 下载 SQL 文件",
            data=final_sql,
            file_name=f"import_{table_name}.sql",
            mime="application/sql"
        )

def render_api_mode(df: pd.DataFrame, mapping: Dict[str, str]):
    """API 调用模式"""
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        method = st.selectbox("请求方法", ["POST", "PUT", "PATCH", "GET"], key="api_method")
    with col2:
        url = st.text_input("API 接口地址", placeholder="https://api.example.com/users", key="api_url")
        
    st.caption("在下方 JSON 中使用 `{{Excel列名}}` 作为占位符。系统会自动替换为 Excel 中的数据。")
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Headers (JSON)**")
        headers_str = st.text_area("Headers", value='{\n  "Content-Type": "application/json",\n  "Authorization": "Bearer YOUR_TOKEN"\n}', height=150, key="api_headers")
        
    # 构建默认的映射 Body 模板 (内核)
    default_payload = {}
    for db_col, excel_col in mapping.items():
        default_payload[db_col] = f"{{{{{excel_col}}}}}"
    
    # 智能构建器 (Smart Builder)
    with st.expander("🛠️ 智能报文组装 (Smart Body Builder)", expanded=True):
        st.info("💡 如果您的 API 报文结构复杂，可在此粘贴浏览器抓取的原始 JSON，然后选择 Excel 数据插入的位置。")
        
        # 1. 输入外壳
        sample_json_str = st.text_area(
            "1. 粘贴原始报文 JSON (Envelope)", 
            height=150,
            placeholder='例如: {"token": "xyz", "data": {"userInfo": ...}}',
            key="smart_builder_input"
        )
        
        # 2. 解析与选择位置
        if sample_json_str:
            try:
                sample_json = json.loads(sample_json_str)
                all_paths = get_json_paths(sample_json)
                
                c_sel, c_act = st.columns([3, 1])
                with c_sel:
                    target_path = st.selectbox(
                        "2. 选择 Excel 数据插入位置 (Target Node)",
                        options=["(替换整个 Body)"] + all_paths,
                        key="smart_builder_path"
                    )
                with c_act:
                    st.write("") # Align
                    st.write("") 
                    if st.button("3. 生成模板", use_container_width=True):
                        if target_path == "(替换整个 Body)":
                            final_template = default_payload
                        else:
                            # 深拷贝以免修改原对象
                            import copy
                            final_template = copy.deepcopy(sample_json)
                            set_value_by_path(final_template, target_path, default_payload)
                        
                        # 更新到下方的 Body 编辑框
                        st.session_state.api_body = json.dumps(final_template, indent=2, ensure_ascii=False)
                        st.toast("模板已更新！请在下方确认。", icon="⬇️")
                        
            except json.JSONDecodeError:
                st.warning("⚠️ 请输入合法的 JSON 格式")
            except Exception as e:
                st.error(f"解析出错: {e}")

    with col_r:
        st.markdown("**Body 模板 (JSON)**")
        # 如果 session_state 中有值则使用，否则使用默认
        initial_body = json.dumps(default_payload, indent=2, ensure_ascii=False)
        if 'api_body' not in st.session_state:
             st.session_state.api_body = initial_body
             
        body_str = st.text_area(
            "Request Body", 
            key="api_body", # 双向绑定
            height=300
        )

    # 预览

    if not df.empty:
        try:
            first_row = df.iloc[0].to_dict()
            
            # 解析模板
            preview_body_str = replace_placeholders(body_str, first_row)
            preview_headers_str = replace_placeholders(headers_str, first_row)
            
            # 校验 JSON
            json.loads(preview_body_str)
            json.loads(preview_headers_str)
            
            with st.expander("👁️ 预览 (第一条数据)", expanded=False):
                st.markdown(f"**Method**: `{method}`")
                st.markdown(f"**URL**: `{url}`")
                st.markdown("**Headers**:")
                st.json(preview_headers_str)
                st.markdown("**Body**:")
                st.json(preview_body_str)
                
        except json.JSONDecodeError as e:
            st.error(f"JSON 格式错误: {e}")
        except Exception as e:
            st.error(f"预览生成失败: {e}")

    st.divider()
    st.markdown("##### 🧪 接口测试与执行")

    # 测试按钮区域
    if st.button("📡 发送测试请求 (仅第一条)", help="使用第一行数据发送一次真实请求，以验证接口连通性"):
        if df.empty:
            st.error("Excel 数据为空，无法测试")
        elif not url:
            st.error("请输入 API 地址")
        else:
            try:
                first_row = df.iloc[0].to_dict()
                req_body = replace_placeholders(body_str, first_row)
                req_headers = replace_placeholders(headers_str, first_row)
                
                start_time = time.time()
                response = requests.request(
                    method=method,
                    url=url,
                    headers=json.loads(req_headers),
                    data=req_body.encode('utf-8'),
                    timeout=10
                )
                elapsed = round(time.time() - start_time, 3)
                
                # 存入 Session State
                st.session_state.last_api_test = {
                    'status': response.status_code,
                    'elapsed': elapsed,
                    'req_body': req_body,
                    'resp_body': response.text
                }
                
                if 200 <= response.status_code < 300:
                    st.toast(f"测试成功! HTTP {response.status_code}", icon="✅")
                else:
                    st.toast(f"测试失败! HTTP {response.status_code}", icon="❌")
                    
            except Exception as e:
                st.error(f"测试请求发送失败: {e}")

    # 展示测试结果
    if 'last_api_test' in st.session_state:
        res = st.session_state.last_api_test
        status_color = "green" if 200 <= res['status'] < 300 else "red"
        st.markdown(
            f"**测试结果**: :{status_color}[HTTP {res['status']}] ⏱️ {res['elapsed']}s"
        )
        
        with st.expander("🔍 查看测试报文详情", expanded=(res['status'] >= 300)):
            c_req, c_resp = st.columns(2)
            with c_req:
                st.markdown("**Request Payload**")
                st.code(res['req_body'], language='json')
            with c_resp:
                st.markdown("**Response Data**")
                try:
                    # 尝试格式化 JSON
                    parsed = json.loads(res['resp_body'])
                    st.json(parsed)
                except:
                    st.text(res['resp_body'])

    st.markdown("---")

    # 执行按钮
    if st.button("🚀 开始批量调用 (所有数据)", type="primary"):
        if not url:
            st.error("请输入 API 地址")
            return
            
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_container = st.container()
        
        success_count = 0
        fail_count = 0
        logs = []
        
        total = len(df)
        
        for index, row in df.iterrows():
            row_dict = row.to_dict()
            try:
                # 准备请求数据
                req_body = replace_placeholders(body_str, row_dict)
                req_headers = replace_placeholders(headers_str, row_dict)
                
                # 发送请求
                response = requests.request(
                    method=method,
                    url=url,
                    headers=json.loads(req_headers),
                    data=req_body.encode('utf-8')
                )
                
                # 记录日志
                if 200 <= response.status_code < 300:
                    success_count += 1
                else:
                    fail_count += 1
                    logs.append(f"❌ Row {index+1}: Failed ({response.status_code}) - {response.text[:100]}")
                    
            except Exception as e:
                fail_count += 1
                logs.append(f"❌ Row {index+1}: Error - {str(e)}")
            
            # 更新进度
            progress_bar.progress((index + 1) / total)
            status_text.text(f"正在处理: {index + 1}/{total} (成功: {success_count}, 失败: {fail_count})")
            
        status_text.text(f"处理完成! 成功: {success_count}, 失败: {fail_count}")
        
        if logs:
            with log_container:
                st.warning("以下请求失败：")
                st.text("\n".join(logs))
        else:
            st.success("所有请求执行成功！")

def replace_placeholders(template: str, data: Dict[str, Any]) -> str:
    """替换字符串中的 {{Key}} 占位符"""
    result = template
    for key, val in data.items():
        placeholder = f"{{{{{key}}}}}"
        if pd.isna(val):
            val_str = "null" # JSON null
            # 这是一个简单的替换，如果 val 是 null 且模板中是 "{{key}}"，则替换结果是 "null"
            # 注意：如果模板是 "key": "{{key}}"，替换后变成 "key": "null"，这是字符串 "null"。
            # 如果期望是 "key": null，则模板应该是 "key": {{key}} (无引号)。
            result = result.replace(placeholder, val_str)
        else:
            # 简单转义双引号和换行符，防止破坏 JSON 结构
            val_str = str(val).replace('"', '\\"').replace('\n', '\\n')
            result = result.replace(placeholder, val_str)
    return result

def get_json_paths(data: Any, prefix: str = "") -> List[str]:
    """递归获取 JSON 所有可能的路径"""
    paths = []
    if isinstance(data, dict):
        for k, v in data.items():
            curr_path = f"{prefix}.{k}" if prefix else k
            paths.append(curr_path)
            paths.extend(get_json_paths(v, curr_path))
    elif isinstance(data, list):
        # 简化处理：对于列表，只取第一个元素作为示例路径，或者不深入
        # 这里选择不深入列表内部，因为替换通常是针对对象Key
        pass
    return paths

def set_value_by_path(data: Dict, path: str, value: Any):
    """根据路径设置字典的值 (引用修改)"""
    keys = path.split('.')
    curr = data
    for i, key in enumerate(keys[:-1]):
        if key in curr:
            curr = curr[key]
        else:
            # 路径不存在则创建
            curr[key] = {}
            curr = curr[key]
    
    # 设置最后一级
    last_key = keys[-1]
    curr[last_key] = value
