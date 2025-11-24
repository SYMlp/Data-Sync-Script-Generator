import os
import sys
import streamlit.web.cli as stcli

def resolve_path(path):
    """获取资源绝对路径 (兼容开发环境和打包后的环境)"""
    if getattr(sys, '_MEIPASS', False):
        # PyInstaller 解压后的临时目录
        return os.path.join(sys._MEIPASS, path)
    # 开发环境当前目录
    return os.path.join(os.getcwd(), path)

if __name__ == "__main__":
    # 1. 构造启动参数，模拟命令行: streamlit run streamlit_app.py --global.developmentMode=false
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("streamlit_app.py"),
        "--global.developmentMode=false",
    ]
    
    # 2. 启动 Streamlit
    sys.exit(stcli.main())

