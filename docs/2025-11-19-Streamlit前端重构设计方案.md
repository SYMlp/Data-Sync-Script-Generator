# 🎨 Streamlit 前端重构设计方案

> **创建日期**: 2025-11-19
> **作者**: 技术产品经理 (TPM)
> **状态**: 已批准 (Approved)
> **关联任务**: [TODO]-002-Streamlit重构

## 1. 背景与目标 (Context & Goals)

### 1.1 问题现状 (As-Is)
当前系统使用 `PySimpleGUI` (`ui.py`) 作为前端界面。
*   **体验差**: 界面风格陈旧（Windows 95 风格），缺乏现代 Web 应用的交互流畅度。
*   **稳定性低**: 单线程模型导致在执行长耗时任务（如连接数据库、生成大脚本）时，界面频繁出现“未响应”假死现象。
*   **操作繁琐**: 生成的 SQL 脚本无法方便地一键复制，缺乏语法高亮。

### 1.2 目标 (To-Be)
使用 **Streamlit** 框架完全重构前端交互层。
*   **现代化**: 采用 Web 风格界面，支持深色模式/浅色模式自适应。
*   **高响应**: 利用 Streamlit 的前后端分离特性和 `st.spinner` 加载状态，彻底解决界面假死问题。
*   **易用性**: 提供多选组件、一键复制、语法高亮等原生高级特性。

## 2. 详细功能设计 (Functional Specifications)

### 2.1 布局架构 (Layout)
页面采用 **侧边栏 (Sidebar) + 主工作区 (Main Area)** 的经典布局。

#### A. 侧边栏：连接配置 (Sidebar: Connection)
**标题**: "🔌 数据库连接"
**组件**:
1.  **Host**: 文本输入框 (默认: `localhost`)
2.  **Port**: 数字输入框 (默认: `3306`)
3.  **Username**: 文本输入框 (默认: `root`)
4.  **Password**: 密码输入框 (type='password')
5.  **Database**: 文本输入框 (必填)
6.  **Connect Button**: "连接数据库" 按钮。

**交互逻辑**:
*   点击连接后，触发后端 `db_connector.connect()`。
*   连接成功：显示 ✅ 绿色成功提示，并将连接对象存储在 `st.session_state` 中。
*   连接失败：显示 ❌ 红色错误信息（包括具体的 Exception）。

#### B. 主工作区：生成配置 (Main Area: Configuration)
**标题**: "🛠️ MySQL 同步脚本生成器"

**Section 1: 表选择 (Table Selection)**
*   **前置条件**: 数据库已连接。否则显示 "👈 请先在左侧连接数据库"。
*   **组件**: `st.multiselect` (多选下拉框)。
    *   **Label**: "选择需要同步的表 (支持搜索)"
    *   **Data Source**: 调用 `metadata_querier.get_all_tables()` 获取。
    *   **功能**: 支持输入文字搜索表名，支持全选（可选实现）。

**Section 2: 同步规则 (Sync Rules)**
*   **组件**: `st.expander` ("高级配置", 默认收起)
    *   `st.checkbox`: "生成 DELETE 语句 (清理目标表旧数据)" (默认: True)
    *   `st.checkbox`: "生成 INSERT 语句" (默认: True)
    *   `st.radio`: "主键冲突处理" -> ["IGNORE", "REPLACE", "UPDATE"] (默认: IGNORE)

**Section 3: 动作与输出 (Action & Output)**
*   **组件**: `st.button` ("🚀 生成同步脚本")
*   **交互逻辑**:
    1.  点击后，显示 `st.spinner("正在分析表结构并生成脚本...")`。
    2.  调用 `sql_generator.generate_script()`。
    3.  成功后，使用 `st.code(sql, language='sql')` 展示结果。
    4.  (可选) `st.download_button`: 允许下载为 `.sql` 文件。

## 3. 技术实现要求 (Technical Requirements)

> **给架构师/开发者的注意事项**

### 3.1 状态管理 (State Management)
Streamlit 是无状态的，每次交互都会重新运行脚本。**必须**使用 `st.session_state` 管理以下对象，防止重连：
*   `db_connector`: 数据库连接实例。
*   `table_list`: 已获取的表名缓存。

### 3.2 资源缓存 (Caching)
建议使用 `@st.cache_resource` 装饰器来管理数据库连接的创建，确保连接池复用。

### 3.3 异常处理 (Error Handling)
所有后端调用（连接、查询、生成）必须包裹在 `try-except` 块中，并使用 `st.error()` 优雅地展示错误堆栈，而不是让页面崩溃。

### 3.4 目录清理 (Cleanup)
*   新入口文件命名为: `streamlit_app.py`。
*   原 `ui.py` 标记为废弃 (Deprecated)，待新版稳定后删除。
*   `requirements.txt` 需添加 `streamlit`。

## 4. 验收标准 (Acceptance Criteria)
1.  [ ] 能够成功连接本地 MySQL 数据库。
2.  [ ] 连接后能正确列出所有表名。
3.  [ ] 多选表后，点击生成，能看到 SQL 代码块。
4.  [ ] SQL 代码块右上角有 "Copy" 图标。
5.  [ ] 整个过程中界面无卡顿、无假死。

