# -*- coding: utf-8 -*-
"""
Bitfinex 放貸機器人打包腳本
使用 PyInstaller 將專案打包成執行檔案
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_executable():
    """建立執行檔案"""
    print("開始打包 Bitfinex 放貸機器人...")
    
    # 檢查 PyInstaller 是否已安裝
    try:
        import PyInstaller
        print(f"PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("PyInstaller 未安裝，正在安裝...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # 獲取專案根目錄
    project_root = Path(__file__).parent
    main_script = project_root / "lending.py"
    
    # PyInstaller 參數
    pyinstaller_args = [
        "pyinstaller",
        "--name", "LendingBot",
        "--onefile",  # 打包成單一執行檔
        "--console",  # 保留控制台視窗
        "--icon", "NONE",  # 無圖示
        "--clean",  # 清除暫存檔
        "--noconfirm",  # 不詢問覆蓋
        
        # 包含必要的檔案 (不包含.env，讓使用者自行設定)
        "--add-data", f"{project_root}/config.py;.",
        "--add-data", f"{project_root}/bitfinex.py;.",
        "--add-data", f"{project_root}/common.py;.",
        "--add-data", f"{project_root}/dynamic_optimizer.py;.",
        "--add-data", f"{project_root}/order_book_monitor.py;.",
        
        # 隱含匯入（避免模組載入問題）
        "--hidden-import", "schedule",
        "--hidden-import", "bitfinex-api-py",
        "--hidden-import", "bfxapi",
        "--hidden-import", "dotenv",
        "--hidden-import", "aiohttp",
        "--hidden-import", "pandas",
        "--hidden-import", "asyncio",
        "--hidden-import", "dynamic_optimizer",
        "--hidden-import", "order_book_monitor",
        
        # 排除不需要的模組（減少檔案大小）
        "--exclude-module", "matplotlib",
        "--exclude-module", "tkinter",
        "--exclude-module", "PIL",
        "--exclude-module", "numpy.distutils",
        
        str(main_script)
    ]
    
    print("正在執行 PyInstaller...")
    print(f"指令: {' '.join(pyinstaller_args)}")
    
    # 執行 PyInstaller
    result = subprocess.run(pyinstaller_args, capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode == 0:
        print("打包成功！")
        
        # 複製重要檔案到 dist 目錄
        dist_dir = project_root / "dist"
        if dist_dir.exists():
            # 複製 .env 範例檔案
            env_example = project_root / ".env"
            if env_example.exists():
                shutil.copy2(env_example, dist_dir / ".env.example")
                print("已複製 .env.example 到 dist 目錄")
            
            # 複製說明文件
            readme_files = ["README.md", "CLAUDE.md"]
            for readme_file in readme_files:
                readme_path = project_root / readme_file
                if readme_path.exists():
                    shutil.copy2(readme_path, dist_dir / readme_file)
                    print(f"已複製 {readme_file} 到 dist 目錄")
        
        print(f"\n打包完成！執行檔位於: {dist_dir / 'LendingBot.exe'}")
        print("\n使用說明:")
        print("1. 將 .env.example 重新命名為 .env")
        print("2. 編輯 .env 填入你的 Bitfinex API 金鑰")
        print("3. 執行 LendingBot.exe 開始放貸")
        
    else:
        print("打包失敗！")
        print("錯誤輸出:")
        print(result.stderr)
        print("\n標準輸出:")
        print(result.stdout)
        return False
    
    return True

def clean_build_files():
    """清除打包產生的暫存檔案"""
    print("\n清理暫存檔案...")
    
    # 要清除的目錄和檔案
    clean_targets = ["build", "LendingBot.spec", "__pycache__"]
    
    project_root = Path(__file__).parent
    
    for target in clean_targets:
        target_path = project_root / target
        if target_path.exists():
            if target_path.is_dir():
                shutil.rmtree(target_path)
                print(f"已清除目錄: {target}")
            else:
                target_path.unlink()
                print(f"已清除檔案: {target}")
    
    print("清理完成")

if __name__ == "__main__":
    print("=" * 60)
    print("  Bitfinex 放貸機器人打包工具")
    print("=" * 60)
    
    try:
        # 建立執行檔
        if create_executable():
            # 清理暫存檔案  
            clean_build_files()
            print("\n所有任務完成！")
        else:
            print("\n打包過程中發生錯誤")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n使用者中斷操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n發生未預期的錯誤: {e}")
        sys.exit(1)