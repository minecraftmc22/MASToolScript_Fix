#!/usr/bin/env python
#-*- coding: utf-8 -*-

import sys, os, json, time
import traceback, requests, tqdm
import TUtil
import TUtilLog
from TUtilLog import info, debug, warning, error
import TTranslation
import TLogo
DOWNLOAD_DDLC_URL = None
PATH = '.'#sys.path[0]
CACHE_PATH = PATH + "/cache"
GAME_PATH = PATH + "/game"
MAS_OWN = "Mon1-innovation"#"Monika-After-Story"
MAS_REP = "MonikaModDev-zhCN"

MON1_REP = "MAS-Simplified-Chinese-Patch"
MON1_OWN = "Mon1-innovation"

debug('文件路径: {}'.format(PATH))
TLogo.moyu()
def print_info(str):
    print(str)
    TUtilLog.info(str)

TUtil.mkdir('./CACHE')

mas_installed = False#TUtil.is_exists(PATH + "/game/masrun")
FileData = None
#print("选择语言/Select Language")
#print("")
#print("1 - 简体中文 (Default)")
#print("2 - English")
#
import requests

def check_link_access(link):
    try:
        response = requests.head(link, verify=False, timeout=(10, 20), allow_redirects=True)
        if response.status_code in [200, 206, 301, 302]:
            return True
        else:
            return False
    except Exception as e:
        error(traceback.format_exc())
        return False


def find_local_manifest():
    """找随程序一起带的 extra_file.json（网络完全不通时的兜底）"""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(PATH, 'extra_file.json'),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'extra_file.json'),
        os.path.join(here, '..', 'extra_file.json'),
        os.path.join(here, 'extra_file.json'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def get_base_file():
    global DOWNLOAD_DDLC_URL
    global FileData
    # 获取基础文件信息
    print_info("获取基础文件信息")
    raw_url = 'https://raw.githubusercontent.com/Mon1-innovation/MAS-Simplified-Chinese-Patch/main/extra_file.json'
    urls = []
    if TUtil.ENABLE_SPEED:
        urls.append("https://releases.0721play.top/" + raw_url)
    urls.append(raw_url)
    urls.append('http://sp2.0721play.icu/d/MAS/MAS-PC/extra_file.json')
    # 依次尝试所有地址，拿到的必须是可以解析的 JSON
    try:
        FileData = TUtil.fetch_json(urls, "基础文件信息")
    except TUtil.ReleaseError:
        local = find_local_manifest()
        if not local:
            raise
        print_info("在线获取清单失败，改用本地清单：{}".format(local))
        TUtilLog.warning("使用本地 extra_file.json，其中的下载链接可能已经过期")
        with open(local, encoding='utf-8') as f:
            FileData = json.load(f)
    if not isinstance(FileData, dict) or "base_files" not in FileData:
        raise Exception("基础文件信息格式异常: {}".format(FileData))
    for file in tqdm.tqdm(FileData["base_files"], desc="基础文件"):
        if DOWNLOAD_DDLC_URL != None:
            continue
        if file[0] == "ddlc.zip":
            if (check_link_access(file[1])):
                DOWNLOAD_DDLC_URL = file[1]
                print_info("设置DDLC链接为：{}".format(file[1]))
                continue
            else:
                print_info("访问失败, 正在尝试更换备用链接")
    if DOWNLOAD_DDLC_URL == None:
        raise Exception("所有DDLC链接全部尝试失败, 无法进行安装!")


def find_asset(assets, matcher):
    """在 [(文件名, 下载链接), ...] 里找出第一个匹配的资产，找不到返回 None"""
    for name, url in assets:
        if matcher(name):
            return name, url
    return None


def download_with_retry(url, path, name):
    """下载失败自动重试一次，返回是否成功"""
    try:
        TUtil.download(url, path, name)
        return True
    except Exception:
        error("下载失败：\n{}".format(traceback.format_exc()))
        print("下载失败，准备重试...")
        print("从github下载可能需要加速器...")
    try:
        TUtil.download(url, path, name)
        return True
    except Exception:
        error("下载失败：\n{}".format(traceback.format_exc()))
        print("下载失败，查看MASToolKit.log获取更多信息")
        return False


# 添加全局silent模式标志
SILENT_MODE = False


def ask_speed():
    """询问是否启用 github release 加速（原来这段只有提示、没有读取输入）"""
    if SILENT_MODE:
        TUtil.ENABLE_SPEED = False
        return
    print_info("是否启用github release加速")
    print_info("github release 直连失败时可以选择开启（走项目的 gh-proxy 镜像）")
    print_info("Y/N(默认)")
    try:
        a = input().strip().lower()
    except EOFError:
        a = ''
    TUtil.ENABLE_SPEED = (a == 'y')
    if TUtil.ENABLE_SPEED:
        print_info("已启用 releases.0721play.top 加速")

def tool_box():
    def cn_update():
        print_info('准备下载汉化补丁')
        try:
            print_info("汉化补丁当前版本：{}".format(TUtil.get_latest_release_tag(MON1_OWN, MON1_REP)))
            print_info('==========================================')
            print_info('更新说明：\n\n' + TUtil.get_latest_release_info(MON1_OWN, MON1_REP))
            print_info('==========================================')
            time.sleep(1)
            assets = TUtil.get_latest_release_dl(MON1_OWN, MON1_REP)
        except TUtil.ReleaseError as e:
            print_info("获取汉化补丁信息失败：{}".format(e))
            print_info("请关闭梯子 / Steam++ / Watt Toolkit 后重试")
            return

        debug(assets)
        for rpa in ('chs.rpa', 'chs_gui.rpa'):
            item = find_asset(assets, lambda n, target=rpa: n == target)
            if item is None:
                TUtilLog.warning("汉化补丁 release 中没有 {}，跳过".format(rpa))
                print_info('未找到 {}，跳过'.format(rpa))
                continue
            print_info('准备下载{}...'.format(rpa))
            if not download_with_retry(item[1], GAME_PATH, rpa):
                raise Exception("{} 下载失败，请检查网络后重试".format(rpa))
    print("===============================")
    if not SILENT_MODE:
        print_info("请选择功能")
        print_info("1. 重装最新版汉化")
        print_info("2. 安装扩展内容（未实现）")
        print_info("3. 退出（默认）")
        a = input()
        if a == '1':
            cn_update()
        elif a == '2':
            pass
        else:
            pass
    else:
        # 静默模式下自动执行重装最新版汉化
        print_info("静默模式：自动重装最新版汉化")
        cn_update()


def main():
    language = None#input()
    if language != '2':
        TTranslation.TARGET_LANG = TTranslation.zhCN
    else:
        TTranslation.TARGET_LANG = TTranslation.en
    _ = TTranslation.get_tl

    if mas_installed:
        info(_("MAS 已经安装"))
        print(_("MAS 已经安装"))
        #print("删除masrun文件即可让本程序覆盖重装")
        ask_speed()
        tool_box()
    else:
        ask_speed()
        try:
            TUtil.get_github_rate_limit()
        except:
            pass
        info(_("未安装 MAS"))
        print(_("未安装 MAS"))
        print(_("准备安装MAS..."))

        # 先确认拿得到 release 信息再开始下载。
        # 旧版是先下 200MB 的 DDLC 才去取版本号，一旦 GitHub 这边出问题
        # （返回空列表 / 被墙 / 限额）前面下好的东西全白费，还直接崩在 IndexError。
        try:
            mas_tag = TUtil.get_latest_release_tag(MAS_OWN, MAS_REP)
        except TUtil.ReleaseError as e:
            print_info("获取 MAS 最新版本失败：{}".format(e))
            print_info("请关闭梯子 / Steam++ / Watt Toolkit 后重试；Github 接口限额为 60 次/小时，稍后再试也可以")
            raise

        masver = TUtil.normalize_tag(mas_tag)
        print('开始下载MAS最新版本')
        info("开始下载MAS最新版本")
        print_info("MAS最新版本为：{}".format(mas_tag))
        print_info('==========================================')
        print_info('Monika After Story {} 更新内容：\n\n'.format(masver))
        print_info('\n' + TUtil.get_latest_release_info(MAS_OWN, MAS_REP))
        print_info('\n\n')
        print_info('==========================================')
        print_info('更新内容已经保存至log文件中')
        print_info('获取下载链接...')
        mas_assets = TUtil.get_latest_release_dl(MAS_OWN, MAS_REP)
        debug(mas_assets)

        # 资产名不一定严格是 Monika_After_Story-<ver>-Mod.zip，放宽匹配
        mas_zip = find_asset(mas_assets, lambda n: n == "Monika_After_Story-{}-Mod.zip".format(masver))
        if mas_zip is None:
            mas_zip = find_asset(mas_assets, lambda n: n.lower().startswith('monika_after_story')
                                 and n.lower().endswith('.zip'))
        if mas_zip is None:
            raise Exception("release {} 里找不到 MAS 主程序压缩包，现有文件：{}".format(
                mas_tag, [n for n, _ in mas_assets]))
        mas_zip_name, mas_zip_url = mas_zip

        print("获取DDLC下载链接...")
        get_base_file()
        info("开始下载DDLC: {}".format(CACHE_PATH))
        TUtil.download(DOWNLOAD_DDLC_URL, CACHE_PATH, 'ddlc.zip')

        print_info('准备下载MAS...')
        if not download_with_retry(mas_zip_url, CACHE_PATH, 'mas.zip'):
            raise Exception("MAS 主程序下载失败")

        spritepacks = find_asset(mas_assets, lambda n: n == 'spritepacks.zip')
        if spritepacks is not None:
            if SILENT_MODE:
                print_info('静默模式：下载精灵包')
                want_sp = True
            else:
                print('是否下载官方精灵包?（未汉化）')
                print('不下载则需要手动安装精灵包')
                print("Y(默认)/N")
                want_sp = input().strip().lower() != 'n'
            if not want_sp:
                print_info('跳过精灵包下载')
            elif not download_with_retry(spritepacks[1], CACHE_PATH, 'spritepacks.zip'):
                print_info('跳过精灵包下载')

        print_info("汉化补丁当前版本：{}".format(TUtil.get_latest_release_tag(MON1_OWN, MON1_REP)))
        print_info('==========================================')
        print_info('更新说明：\n\n' + TUtil.get_latest_release_info(MON1_OWN, MON1_REP))
        print_info('==========================================')
        time.sleep(2)
        patch_assets = TUtil.get_latest_release_dl(MON1_OWN, MON1_REP)
        debug(patch_assets)
        for rpa in ('chs.rpa', 'chs_gui.rpa'):
            item = find_asset(patch_assets, lambda n, target=rpa: n == target)
            if item is None:
                TUtilLog.warning("汉化补丁 release 中没有 {}，跳过".format(rpa))
                print_info('未找到 {}，跳过'.format(rpa))
                continue
            print_info('准备下载{}...'.format(rpa))
            if not download_with_retry(item[1], CACHE_PATH, rpa):
                raise Exception("{} 下载失败，请检查网络后重试".format(rpa))

        print_info('开始解压文件')
        print_info('解压ddlc')
        if TUtil.is_exists(CACHE_PATH + '/ddlc.zip'):
            TUtil.un_zip(CACHE_PATH + '/ddlc.zip')
        print_info('解压MAS')
        if TUtil.is_exists(CACHE_PATH + '/mas.zip'):
            TUtil.un_zip(CACHE_PATH + '/mas.zip')
        
        
        print_info('安装MAS...')
        #TUtil.copy_dir(CACHE_PATH + '/mas.zip_files', CACHE_PATH + '/ddlc.zip_files/DDLC-1.1.1-pc')
        TUtil.dir_check(CACHE_PATH + '/mas.zip', CACHE_PATH + '/ddlc.zip_files/DDLC-1.1.1-pc')
        #print_info('安装MAS汉化补丁...')
        if TUtil.is_exists(CACHE_PATH + '/chs.rpa'):
            print_info('安装汉化补丁...')
            TUtil.copy(CACHE_PATH + '/chs.rpa', CACHE_PATH + '/ddlc.zip_files/DDLC-1.1.1-pc/game')
        if TUtil.is_exists(CACHE_PATH + '/chs_gui.rpa'):
            print_info('安装字体...')
            TUtil.copy(CACHE_PATH + '/chs_gui.rpa', CACHE_PATH + '/ddlc.zip_files/DDLC-1.1.1-pc/game')
        if TUtil.is_exists(CACHE_PATH + '/spritepacks.zip'):
            TUtil.un_zip(CACHE_PATH + '/spritepacks.zip')
            print_info('安装精灵包...')
            TUtil.dir_check(CACHE_PATH + '/spritepacks.zip', CACHE_PATH + '/ddlc.zip_files/DDLC-1.1.1-pc')
        try:
            TUtil.get_extra_file(FileData)
        except Exception as e:
            print_info("安装额外内容失败, 跳过")
            TUtilLog.warning("{}".format(traceback.format_exc()))
        print_info('移出缓存文件夹...')
        TUtil.copy_dir(CACHE_PATH + '/ddlc.zip_files/DDLC-1.1.1-pc', PATH)
        print_info('MAS安装完成~')
        print_info('ENJOY 你的莫妮卡~')
        print("======================================")