# 🛡️ SqlGenerator 维护与修改指南

> **重要**: 修改本目录下的 `sql_generator.py` 时，请务必阅读本指南。该类是系统的核心工厂，其变动具有广泛的连锁反应。

## 1. 核心职责
`SqlGenerator` 负责将 `SyncConfig`（配置对象）和 `MetaDataQuerier`（元数据）转化为可执行的 MySQL 存储过程脚本。

它提供两种输出模式：
1.  **分段输出 (`generate_script`)**: 返回 `{'definition', 'call', 'drop'}` 字典。用于精细控制执行流程（如 `main.py`）。
2.  **完整输出 (`generate_full_executable_script`)**: 返回拼接好的单一 SQL 字符串。用于 UI 展示和文件下载。

## 2. 联动修改检查清单 (Impact Analysis)

当你修改了 `sql_generator.py` 的逻辑后，**必须**检查以下文件以确保系统一致性：

### A. 前端展示 (`streamlit_app.py`)
*   **受影响点**: `generate_script()` 函数中的 **预览** 和 **下载** 逻辑。
*   **检查项**:
    *   如果你修改了 `generate_full_executable_script` 的拼接顺序，请确认前端下载的 SQL 文件是否依然符合 "Drop -> Create -> Call -> Drop" 的幂等逻辑。
    *   如果你修改了 `generate_script` 的返回 Key（例如把 `definition` 改名为 `body`），前端会直接报错。

### B. 后端调试入口 (`main.py`)
*   **受影响点**: `main()` 函数中的 **分步执行** 逻辑。
*   **检查项**:
    *   `main.py` 依赖 `generate_script` 返回的字典进行分步执行（先 `execute(def)` 再 `execute(call)`）。
    *   如果你更改了字典结构，必须同步更新 `main.py` 中的 `sql_parts[...]` 调用。

### C. 导出工具 (`src/utils/file_exporter.py`)
*   **受影响点**: 虽然目前 UI 直接使用了 Generator 的输出，但如果有遗留代码使用 `FileExporter`，需确认其是否兼容新的脚本格式。

## 3. 常见陷阱 (Pitfalls)

1.  **游标陷阱**:
    *   在生成循环逻辑时，切记 `SELECT ... INTO` 必须包裹在独立的 `BEGIN ... END` 块中，并定义局部的 `CONTINUE HANDLER`。否则，一旦查询为空，全局的 `NOT FOUND` Handler 会被触发，导致外层循环意外终止。
    *   *相关方法*: `_generate_main_table_sync_logic`

2.  **类型映射**:
    *   `_get_column_sql_type` 目前手动处理了常见类型。如果引入新的 MySQL 数据类型（如 JSON, Spatial Types），必须在此处添加映射，否则生成的 `DECLARE` 语句会报错。

3.  **幂等性**:
    *   生成的脚本必须是**幂等的**。即：无论运行多少次，结果都应该是一致的，且不会报错（这也是为什么我们需要 `DROP PROCEDURE IF EXISTS`）。

