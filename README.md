# 🛠️ MySQL 主从表数据同步脚本生成器 (Data Sync Script Generator)

> **一个可视化的、防呆的、基于 MySQL 存储过程的数据同步解决方案。**
> 
> 专为解决复杂的跨库主从表同步难题而生，自动处理事务边界、游标循环和数据清洗逻辑。

---

## 📖 项目简介 (Introduction)

在数据库运维和开发测试中，我们经常面临这样的挑战：需要将生产环境或测试环境中的**主从关联数据**（如“订单主表”+“订单明细表”）同步到另一个环境。

手写 SQL 脚本不仅繁琐，而且极易出错：
*   如何保证主从表 ID 的一致性？
*   如何处理目标库已存在的记录（Update vs Insert）？
*   如何处理需要删除的旧从表记录？
*   如何在同步过程中保证数据一致性？

**本工具正是为了解决这些痛点而设计的。** 它提供了一个基于 Streamlit 的 Web 界面，让用户通过简单的下拉选择和配置，即可自动生成高质量、包含完整错误处理和事务控制的 MySQL 存储过程脚本。

## ✨ 核心特性 (Key Features)

*   **🎨 可视化交互 (Visual & Intuitive)**:
    *   基于 Streamlit 的现代化 UI，自动加载数据库表结构。
    *   **智能联动**: 选定主表后，自动推荐关联的从表和外键字段。
    *   **可视化过滤器**: 像搭积木一样构建 `WHERE` 过滤条件，支持实时 SQL 预览。

*   **🛡️ 安全防御 (Safety First)**:
    *   **自杀式配置阻断**: 内置逻辑检测源库和目标库是否冲突，防止误操作清空源数据。
    *   **微事务控制**: 生成的脚本在循环内部使用 `START TRANSACTION ... COMMIT`，确保单条主记录及其从记录的原子性，避免长事务锁表。

*   **🧠 智能生成 (Smart Generation)**:
    *   **自动类型映射**: 自动识别 `VARCHAR`, `DECIMAL` 等字段类型并生成正确的变量声明。
    *   **增量同步逻辑**: 自动生成 `INSERT` (新增), `UPDATE` (变更), `DELETE` (清理无用从表数据) 的全套逻辑。
    *   **字段排除**: 支持一键排除审计字段（如 `create_time`, `update_user`），避免覆盖目标库的时间戳。

*   **📦 开箱即用 (Ready to Run)**:
    *   提供配套的打包脚本，可一键生成独立的 `.exe` 可执行文件，无需 Python 环境即可运行。

## 🚀 快速开始 (Quick Start)

### 1. 环境准备

确保已安装 Python 3.8+。

```bash
# 克隆项目
git clone <repository_url>

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动应用

```bash
streamlit run streamlit_app.py
```

应用启动后，浏览器将自动打开 `http://localhost:8501`。

### 3. 打包为 EXE (可选)

如果您需要将工具分发给没有 Python 环境的同事：

```bash
# Windows 环境下
python scripts/build.py
```
构建完成后，`dist/` 目录下将生成 `MySQL脚本生成器.exe`。

## 🗺️ 项目导航 (Navigation)

本项目采用**AI 角色化驱动**的开发模式。如果您是开发者，以下文档将帮助您快速上手：

*   **[🗺️ 项目导航地图 (Project Navigation Map)](docs/项目导航地图.md)**: **强烈推荐阅读**。这是项目的“上帝视角”地图，详细标注了核心类、数据流向和潜在的风险点。
*   **`src/generator/sql_generator.py`**: 核心业务逻辑所在，负责 SQL 拼接。
*   **`prompts-library/`**: AI 协作资产库，定义了本项目背后的 AI 专家团队。

## 🛠️ 技术栈 (Tech Stack)

*   **Frontend**: [Streamlit](https://streamlit.io/) (Web GUI)
*   **Database**: [PyMySQL](https://pymysql.readthedocs.io/) (DB Connector)
*   **Distribution**: [PyInstaller](https://pyinstaller.org/) (Executable Build)
*   **Collaboration**: Cursor AI + Markdown-driven Development

## 📜 许可证 (License)

[MIT License](LICENSE)
