import os
import subprocess
import shutil
import sys
import time
import errno
import stat

def handle_remove_readonly(func, path, exc):
    """
    shutil.rmtree 的回调函数，用于处理只读文件的删除。
    当遇到 PermissionError (EACCES) 时，尝试修改文件权限为可写，然后再次尝试删除。
    """
    excvalue = exc[1]
    # 检查是否是权限错误 (EACCES)
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        # 修改权限为可写
        os.chmod(path, stat.S_IWRITE)
        # 再次尝试执行删除操作
        func(path)
    else:
        # 如果是其他错误，直接抛出
        raise

def retry_rmtree(path, max_retries=3, delay=2):
    """
    带重试机制的目录删除函数。
    如果删除失败（通常是因为文件被占用），会等待后重试。
    """
    if not os.path.exists(path):
        return

    print(f"🧹 正在清理旧目录: {path}...")
    
    for attempt in range(max_retries):
        try:
            # 使用 onerror 处理只读文件的情况 (如 git 目录或某些编译产物)
            shutil.rmtree(path, onerror=handle_remove_readonly)
            print(f"✅ 已清理: {path}")
            return
        except OSError as e:
            # 检查是否是 WinError 5 (Access Denied) 或 WinError 32 (File used by another process)
            # 注意: PermissionError 是 OSError 的子类
            if e.errno == errno.EACCES or e.winerror == 5 or e.winerror == 32:
                if attempt < max_retries - 1:
                    print(f"   ⚠️ 目录被占用，{delay}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    print(f"\n❌ 错误: 无法删除目录 '{path}'")
                    print(f"   原因: {e.strerror} (WinError {e.winerror})")
                    print("💡 提示: 请检查是否有正在运行的 'MySQL脚本生成器' 程序或资源管理器打开了该目录。")
                    print("   请手动关闭相关程序后重试。")
                    # 我们可以选择抛出异常终止构建，或者让用户按键确认后再次尝试
                    raise e
            else:
                # 其他类型的错误直接抛出
                raise e

def clean_build_dirs():
    """清理旧的构建文件夹"""
    # 仅清理 build 目录，保留 dist 目录以支持多版本共存
    dirs_to_clean = ['build'] 
    for d in dirs_to_clean:
        retry_rmtree(d)

def check_requirements():
    """检查必要依赖"""
    print("🔍 正在检查环境依赖...")
    
    # 1. 检查 PyInstaller
    try:
        import PyInstaller
        print("   ✅ PyInstaller 已安装")
    except ImportError:
        print("   ❌ 未检测到 PyInstaller")
        print("   请运行: pip install pyinstaller")
        sys.exit(1)
    
    # 2. 检查 Streamlit
    try:
        import streamlit
        print("   ✅ Streamlit 已安装")
    except ImportError:
        print("   ❌ 未检测到 Streamlit")
        print("   请运行: pip install streamlit")
        sys.exit(1)

    # 3. 检查并自动安装 tqdm (新增)
    try:
        import tqdm
        print("   ✅ tqdm 已安装")
    except ImportError:
        print("   ❌ 未检测到 tqdm")
        print("   请运行: pip install tqdm")
        sys.exit(1)

def build_exe():
    """执行打包命令"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    run_script = os.path.join(project_root, "run.py")
    
    # 使用环境变量控制输出文件名，方便打 Win7 版本
    exe_name = os.environ.get("EXE_NAME", "MySQL脚本生成器")
    dist_dir = os.path.join(project_root, 'dist')
    target_exe = os.path.join(dist_dir, exe_name + ".exe")

    # --- 新增：靶向清理与占用检查 ---
    if os.path.exists(target_exe):
        print(f"♻️  检测到旧版本文件: {target_exe}")
        try:
            os.remove(target_exe)
            print("   ✅ 已清理旧版本")
        except OSError as e:
            print(f"   ❌ 无法删除旧文件！文件可能正在运行。")
            print(f"   原因: {e.strerror}")
            print("   💡 请手动关闭程序后按回车重试，或 Ctrl+C 取消...")
            input() # 等待用户处理
            try:
                os.remove(target_exe) # 二次尝试
                print("   ✅ 已清理旧版本")
            except OSError:
                 print("   ❌ 仍然无法删除，正在退出...")
                 sys.exit(1)
    # ------------------------------
    
    # 使用 sys.executable 确保使用的是当前环境的 Python 解析器
    # 使用 -m PyInstaller 确保调用的是当前环境下的模块
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed", 
        # "--console",
        "--name", exe_name,
        "--clean",
        
        # 核心收集策略：强力收集 Streamlit 及其常用依赖
        "--collect-all", "streamlit",
        "--collect-all", "altair",
        "--collect-all", "pandas", 
        
        # 完整元数据复制策略 (Robustness)
        # 即使某些库当前未直接使用，保留元数据也能防止未来隐式调用报错
        "--copy-metadata", "streamlit",
        "--copy-metadata", "packaging",
        "--copy-metadata", "tqdm",      # 进度条支持
        "--copy-metadata", "regex",     # 正则支持
        "--copy-metadata", "requests",  # 网络请求支持
        "--copy-metadata", "filelock",  # 文件锁支持
        "--copy-metadata", "numpy",     # 数值计算支持
        
        # 递归收集 Streamlit 的所有子模块元数据
        "--recursive-copy-metadata", "streamlit",
        
        # 添加数据文件: 源路径;目标路径 (Windows使用分号;)
        "--add-data", f"streamlit_app.py;.",
        "--add-data", f"src;src",
        "--add-data", f"prompts-library;prompts-library",
        
        "--hidden-import", "src",
        run_script
    ]

    print("\n🚀 开始打包，请稍候...")
    print(f"📂 项目根目录: {project_root}")
    print(f"ℹ️  使用 Python: {sys.executable}")
    print(f"📜 执行命令: {' '.join(cmd)}\n")

    try:
        subprocess.check_call(cmd, cwd=project_root)
        print("\n" + "="*50)
        print("🎉 打包成功！")
        
        # --- 新增：自动复制配置文件 ---
        dist_dir = os.path.join(project_root, 'dist')
        profile_src = os.path.join(project_root, "connection_profiles.json")
        profile_dst = os.path.join(dist_dir, "connection_profiles.json")
        
        if os.path.exists(profile_src):
            print(f"📦 正在复制配置文件...")
            shutil.copy2(profile_src, profile_dst)
            print(f"   ✅ 已复制: connection_profiles.json")
        # ---------------------------

        print("="*50)
        print(f"👉 可执行文件位置: {os.path.join(project_root, 'dist', exe_name + '.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 打包失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("="*50)
    print("   MySQL脚本生成器 - 自动构建脚本")
    print("="*50)
    
    clean_build_dirs()
    check_requirements()
    build_exe()
    
    print("\n按任意键退出...")
    input()
