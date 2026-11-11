import argparse
import sys

# 输出被重定向到管道/文件时（CI、日志重定向），Windows 默认用本地代码页（英文系统是 cp1252），
# 打印中文提示会抛 UnicodeEncodeError 直接把进程打成退出码 1。统一按 UTF-8 输出。
if not sys.stdout.isatty():
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import TUtilLog, TUtil, time

def main(silent=False):
    try:
        # 导入MASToolKit时传入silent参数
        import MASToolKit
        MASToolKit.SILENT_MODE = silent
        MASToolKit.main()
        if not silent:
            print("--按下回车后退出--")
            input()

        TUtil.tool_clear()

    except Exception as e:
        TUtil.print_info("=========================================")
        TUtil.print_info('发生异常，MASTookKit即将退出...')
        TUtil.print_info('查看MASToolKit.log获取详细信息...')
        TUtil.print_info("=========================================")
        TUtil.print_info("异常原因：{}".format(e))
        TUtilLog.exception()

        if not silent:
            print("--按下回车后退出--")
            input()
            # 只有手动运行时才询问要不要删缓存，静默模式直接保留，方便复用已下载的文件
            TUtil.tool_clear(True)
        else:
            TUtil.print_info("保留缓存目录，可再次运行以复用已下载的文件")

if __name__ == '__main__':
    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description='MAS Tool Installer')
    parser.add_argument('--silent', action='store_true', help='运行时不需要用户输入')

    # 解析参数
    args = parser.parse_args()

    # 调用主函数，传入silent标志
    main(silent=args.silent)

    #pyinstaller -F .\Tools\MasInstaller.py