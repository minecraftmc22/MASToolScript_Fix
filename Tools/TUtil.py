#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import shutil
import TUtilLog
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
import traceback
import zipfile
from tqdm import tqdm
import threading



_install_completed = None
ENABLE_SPEED = False

def set_proxy(port):
    os.environ["http_proxy"] = "http://127.0.0.1:{}".format(port)
    os.environ["https_proxy"] = "https://127.0.0.1:{}".format(port)
    print_info("代理地址设置为: '{}'".format("127.0.0.1:{}".format(port)))
def un_zip(file_name):
    """
    解压文件
    """
    import zipfile
    TUtilLog.info("解压文件：'{}'".format(file_name))
    try:
        zip_file = zipfile.ZipFile(file_name)
    except Exception as e:
        TUtilLog.error("解压文件失败：'{}'".format(e))
        return False
    try:
        if os.path.isdir(file_name + "_files"):
            pass
        else:
            os.mkdir(file_name + "_files")
        for names in tqdm(zip_file.namelist(), "解压文件"):
            zip_file.extract(names, file_name + "_files/")
        zip_file.close()
        return True
    except Exception as e:
        TUtilLog.error("解压文件失败：'{}'".format(e))
        zip_file.close()
        return False


GITHUB_API = "https://api.github.com"
API_TIMEOUT = 20
# 有些镜像（OneDrive/SharePoint 之类）会挑 User-Agent，带上更稳
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MASToolKit"}
# 缓存 release 信息，避免同一次运行内反复请求同一个仓库（未登录时限额只有 60 次/小时）
_release_cache = {}


class ReleaseError(Exception):
    """无法从 GitHub 获取 release 信息（网络不通 / 触发限额 / 仓库没有已发布的 release）"""


def normalize_tag(tag):
    """把 tag 统一成不带前缀的版本号: 'v0.12.20' -> '0.12.20'"""
    return str(tag).strip().lstrip("vV")


def _ver_tuple(ver):
    """把 'v0.12.20' / '0.12.20.1' / ['0', '12', '20'] 转成可比较的整数元组"""
    if isinstance(ver, (list, tuple)):
        ver = ".".join(str(x) for x in ver)
    parts = []
    for item in str(ver).strip().lstrip("vV").split("."):
        num = ""
        for ch in item:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts)


def _github_json(url):
    """GET 一个 github api 地址并返回 json，任何异常都转成 ReleaseError"""
    last_error = None
    # 网络抖动（尤其国内直连 github）重试一次，别为一次 EOF 就把安装打断
    for attempt in range(2):
        try:
            resp = requests.get(url, verify=False, timeout=API_TIMEOUT, headers=HEADERS)
        except requests.exceptions.RequestException as e:
            last_error = e
            time.sleep(1)
            continue
        if resp.status_code == 403:
            raise ReleaseError("GitHub 拒绝了请求（403），可能触发了速率限制或被代理/加速器拦截")
        if resp.status_code == 404:
            raise ReleaseError("GitHub 上找不到该 release（404）")
        if resp.status_code != 200:
            raise ReleaseError("GitHub 返回了异常状态码：{}".format(resp.status_code))
        try:
            return resp.json()
        except ValueError:
            raise ReleaseError("GitHub 返回的内容不是合法 JSON（可能被加速器/代理劫持）")
    raise ReleaseError("无法连接 GitHub（{}）".format(last_error))


def fetch_json(urls, desc="文件", rounds=2):
    """
    依次尝试多个地址，返回第一个能正常解析的 JSON

    IN:
        urls   - 地址列表（按优先级排列）
        desc   - 出错提示里显示的名字
        rounds - 所有地址最多轮几遍（raw.githubusercontent 这类地址经常抽风，
                 隔两秒重来一遍往往就好了）
    """
    errors = []
    for round_idx in range(rounds):
        for url in urls:
            try:
                resp = requests.get(url, verify=False, timeout=API_TIMEOUT, headers=HEADERS)
                if resp.status_code == 200:
                    return resp.json()
                errors.append("{} -> HTTP {}".format(url, resp.status_code))
            except Exception as e:
                errors.append("{} -> {}".format(url, e))
        if round_idx < rounds - 1:
            time.sleep(2)
    TUtilLog.error("{}获取失败：{}".format(desc, "；".join(errors)))
    raise ReleaseError("{}获取失败，所有备用地址均不可用".format(desc))


def get_latest_release(own, rep):
    """
    获取仓库最新的 release 信息（同一次运行内只请求一次）

    旧版直接取 /releases 列表的 [0]，当仓库返回空列表（HTTP 200 + "[]"）时
    会抛出 IndexError 直接把整个安装流程打断。这里改用 /releases/latest，
    并对空列表、非 JSON、限额等所有情况给出明确错误。
    """
    key = (own, rep)
    if key in _release_cache:
        cached = _release_cache[key]
        if isinstance(cached, ReleaseError):
            raise ReleaseError(str(cached))
        return cached

    try:
        try:
            data = _github_json("{}/repos/{}/{}/releases/latest".format(GITHUB_API, own, rep))
        except ReleaseError as e:
            # /releases/latest 不可用时退回列表接口，取第一条
            TUtilLog.warning("获取 {}/{} 的 latest release 失败，改用 releases 列表：{}".format(own, rep, e))
            data = _github_json("{}/repos/{}/{}/releases".format(GITHUB_API, own, rep))
            if not isinstance(data, list) or not data:
                raise ReleaseError("仓库 {}/{} 没有已发布的 release（返回空列表）".format(own, rep))
            data = data[0]

        if not isinstance(data, dict) or not data.get("tag_name"):
            raise ReleaseError("仓库 {}/{} 的 release 信息格式异常".format(own, rep))
    except ReleaseError as e:
        _release_cache[key] = e
        raise ReleaseError(str(e))

    _release_cache[key] = data
    return data


def get_github_rate_limit():
    try:
        a = requests.get(GITHUB_API + '/rate_limit', verify=False, timeout=API_TIMEOUT).json()
        remaining = a['resources']['core']['limit'] - a['resources']['core']['used']
        if remaining < 1:
            print("您已经到达Github请求上限，请等待一段时间后重试。")
            TUtilLog.warning('您已经到达Github请求上限，请等待一段时间后重试。')
            return False
        elif remaining < 5:
            print("!!您即将到达Github请求上限，本次安装可能会失败。!!")
            TUtilLog.warning('您即将到达Github请求上限，本次安装可能会失败。')
            return False
    except Exception as e:
        # 拿不到限额信息不影响安装，记录一下就够了
        TUtilLog.warning("读取 Github 限额信息失败：{}".format(e))


def get_latest_release_tag(own, rep):
    """
    获取仓库最新release的tag
    IN:
        own - 拥有者
        rep - 存储库名称
    Return:
        tag 类似于"v0.12.1"
    Raises:
        ReleaseError - 无法获取时
    """
    return get_latest_release(own, rep)['tag_name']


def check_update(oldver, own, rep):
    """
    从github检查是否有更新

    IN:
        oldver - 当前版本号['0', '12', '11']
        own - 拥有者
        rep - 存储库

    RETURNS:
        False - 无更新 / 检查失败
        新版本号 - 返回版本号 v0.12.11.3
    """
    try:
        ver = get_latest_release_tag(own, rep)
        if _ver_tuple(ver) > _ver_tuple(oldver):
            return ver
        return False
    except Exception as e:
        TUtilLog.error("检查更新时发生异常: {}".format(e))
        return False


def get_latest_release_info(own, rep):
    """
    获取仓库最新release的更新信息
    IN:
        own - 拥有者
        rep - 存储库名称
    Return:
        md 源文件
    """
    try:
        return get_latest_release(own, rep).get('body') or "（该版本没有填写更新说明）"
    except Exception as e:
        TUtilLog.error("获取更新信息失败：{}".format(e))
        return "更新信息获取失败"


def get_latest_release_dl(own, rep):
    """
    获取仓库的最新release
    IN:
        own - 拥有者
        rep - 存储库名称
    Return:
        [(文件名, 下载链接), ...]
    Raises:
        ReleaseError - 无法获取时
    """
    assets = get_latest_release(own, rep).get('assets') or []
    result = []
    for items in assets:
        name = items.get('name')
        url = items.get('browser_download_url')
        if name and url:
            result.append((name, url))
    return result


def is_exists(path):
    try:
        return os.path.exists(path)
    except Exception as e:
        TUtilLog.error("{}".format(traceback.format_exc()))
        return False


def mkdir(path):
    os.makedirs(path, exist_ok=True)

# https://blog.csdn.net/weixin_43347550/article/details/105248223

import os
import requests
import traceback
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

def single_thread_download(final_url, file_path, name, chunk_size=1024*1024):
    print("开始单线程普通下载...")
    with requests.get(final_url, stream=True, verify=False, allow_redirects=True,
                      timeout=(15, 60)) as response:
        if response.status_code != 200:
            raise Exception("下载失败，服务器返回状态码: {}".format(response.status_code))
        if 'Content-Length' in response.headers:
            data_size = int(response.headers['Content-Length']) / 1024 / 1024
        else:
            data_size = None
        with open(file_path, 'wb') as f:
            for data in tqdm(
                iterable=response.iter_content(chunk_size),
                total=int(data_size + 1) if data_size else None,
                desc=name,
                unit='MB'
            ):
                f.write(data)
    print(f"单线程下载完成，文件已保存至: {file_path}")

MIRROR_PREFIX = "https://releases.0721play.top/"


def build_url_candidates(url):
    """
    给一个下载地址列出可用的候选地址
    raw.githubusercontent.com 在国内经常直接 SSL 握手失败（连不上），
    所以直连之外再补一个项目镜像做兜底；开了加速开关则镜像优先。
    """
    candidates = [url]
    if ("github.com" in url or "raw.githubusercontent.com" in url) and "0721play" not in url:
        if ENABLE_SPEED:
            candidates = [MIRROR_PREFIX + url, url]
        else:
            candidates = [url, MIRROR_PREFIX + url]
    result = []
    for item in candidates:
        if item not in result:
            result.append(item)
    return result


def download(url, path, name, chunk_size=1024*1024, thread_count=8):
    """下载文件，直连失败时自动换镜像再试一次"""
    last_error = None
    candidates = build_url_candidates(url)
    for index, candidate in enumerate(candidates):
        TUtilLog.debug("请求下载链接: '{}'".format(candidate))
        try:
            _download_once(candidate, path, name, chunk_size, thread_count)
            return
        except Exception as e:
            last_error = e
            TUtilLog.warning("下载失败：{}\n{}".format(candidate, traceback.format_exc()))
            if index < len(candidates) - 1:
                print_info("下载失败，改用备用镜像重试：{}".format(name))
    raise Exception("{} 下载失败：{}".format(name, last_error))


def _download_once(url, path, name, chunk_size=1024*1024, thread_count=8):

    if not os.path.exists(path):
        os.makedirs(path)

    file_path = os.path.join(path, name)
    # 同一个地址最多试 3 次；再多也是白等，不如尽快换镜像
    failtime = 2

    while True:
        try:
            head_resp = requests.head(url, verify=False, allow_redirects=True, timeout=(15, 30))
            if head_resp.status_code >= 400:
                raise Exception("预检请求失败，服务器返回状态码: {}".format(head_resp.status_code))
            file_size = int(head_resp.headers.get('Content-Length', 0))
            accept_ranges = head_resp.headers.get('Accept-Ranges', '').lower()
            final_url = head_resp.url
            TUtilLog.debug(f"HEAD 响应头: {head_resp.headers}")
            TUtilLog.debug(f"最终跳转后的下载链接: {final_url}")

            # 缓存里已经有完整文件（大小一致）就不再重复下载
            if file_size > 0 and os.path.exists(file_path) and os.path.getsize(file_path) == file_size:
                print("已存在完整文件，跳过下载：{}".format(file_path))
                TUtilLog.info("复用已下载文件：'{}'".format(file_path))
                return

            if accept_ranges == 'bytes' and file_size > 0:
                print(f"服务器支持断点续传，尝试多线程下载（{thread_count}线程）")

                def download_chunk(start, end, idx):
                    headers = {'Range': f'bytes={start}-{end}'}
                    part_file = f"{file_path}.part{idx}"
                    with requests.get(final_url, headers=headers, stream=True, verify=False,
                                      timeout=(15, 60)) as r:
                        if r.status_code != 206:
                            raise Exception(f"服务器未正确返回分段内容，状态码: {r.status_code}")
                        if 'Content-Range' not in r.headers:
                            raise Exception("服务器未返回 Content-Range，可能不支持分段下载")
                        with open(part_file, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    f.write(chunk)

                try:
                    # 大小<1MB 直接单线程下载
                    if file_size < chunk_size:
                        print("文件小于最小分块大小，使用单线程下载...")
                        single_thread_download(final_url, file_path, name, chunk_size)
                        return
                    part_size = file_size // thread_count
                    ranges = [
                        (i * part_size, (i + 1) * part_size - 1 if i < thread_count - 1 else file_size - 1, i)
                        for i in range(thread_count)
                    ]

                    with ThreadPoolExecutor(max_workers=thread_count) as executor:
                        futures = {executor.submit(download_chunk, start, end, idx): idx for start, end, idx in ranges}

                        pbar = tqdm(total=file_size, unit='B', unit_scale=True, desc=name)
                        try:
                            while True:
                                downloaded = sum(
                                    os.path.getsize(f"{file_path}.part{i}") if os.path.exists(f"{file_path}.part{i}") else 0
                                    for i in range(thread_count)
                                )
                                pbar.n = downloaded
                                pbar.refresh()
                                if all(f.done() for f in futures):
                                    break
                                time.sleep(0.2)
                        finally:
                            pbar.close()

                        for future in futures:
                            if future.exception():
                                raise future.exception()

                    # 合并
                    print("所有分段下载完成，开始合并文件...")
                    with open(file_path, 'wb') as outfile:
                        for i in range(thread_count):
                            part_file = f"{file_path}.part{i}"
                            with open(part_file, 'rb') as infile:
                                outfile.write(infile.read())
                            os.remove(part_file)
                    print(f"下载完成，文件已保存至: {file_path}")

                except Exception as e:
                    print(f"多线程下载失败: {e}\n自动切换到单线程普通下载...")
                    single_thread_download(final_url, file_path, name, chunk_size)

            else:
                # 直接单线程
                single_thread_download(final_url, file_path, name, chunk_size)

            break
        except Exception as e:
            print('出现异常! 自动重试中...')
            TUtilLog.warning("{}".format(traceback.format_exc()))
            failtime -= 1
            if failtime < 0:
                raise Exception("资源获取失败！请稍后再试！")
            time.sleep(1)
def tool_clear(ask = False):
    import shutil
    clear = True
    if ask:
        clear = False
        print("清除缓存？(Y/N，默认N)")
        try:
            a = input().strip().lower()
        except EOFError:
            a = ''
        if a == 'y':
            clear = True
        else:
            print("保留缓存（下次安装可以直接复用已下载的文件）")
            TUtilLog.info("用户选择保留缓存")

    if not clear:
        return
    try:
        if os.path.isdir('./cache'):
            print("清除缓存...")
            TUtilLog.info("清除缓存...")
            shutil.rmtree('./cache')
    except Exception:
        TUtilLog.exception()
    finally:
        import os
        os._exit(0)

def print_info(message):
    print(message)
    TUtilLog.info(message)

def check_zip(path="./", targetdir = './'):
    dirs = os.listdir(path)

    for _file in tqdm(dirs, desc="安装内容"):
        if not _file.lower().endswith('.zip'):
            continue
        full_path = os.path.join(path, _file)
        if un_zip(full_path):
            dir_check(full_path, targetdir)
        else:
            print_info("精灵包文件处理失败")
            try:
                os.remove(full_path)
            except OSError as e:
                TUtilLog.error("删除损坏的压缩包失败：{}".format(e))
            TUtilLog.error("\n处理出错的文件: '{}'\n".format(_file))
            continue


def dir_check(filedir, path):
    """
    精灵包文件检查流程
    IN:
        filedir - 检查的扩展包压缩包名（先调用解压函数完成后）
        path - MAS所在的文件夹，类似于renpy.config.basedir
    """
    path=path.replace('//', '/')
    subfile = os.listdir(filedir+"_files")
    for i in tqdm(subfile, desc="复制文件"):
        ifull = filedir + "_files" + "/" + i
        if copy_dir_m(i, ifull, path):
            # 处理成功
            continue
        else:
            # 处理名字不正常的文件
            # 进入文件夹后再遍历文件进行处理
            TUtilLog.info("进入文件夹 '{}' 处理内部文件".format(ifull))
            if not os.path.isdir(ifull):
                TUtilLog.info("不是文件夹 '{}' ".format(ifull))
                continue
            subi = os.listdir(ifull)
            for subifile in subi:
                subifile_full = ifull + "/" + subifile
                if copy_dir_m(subifile, subifile_full, path ):
                    continue
                else:
                    TUtilLog.info(
                        "2 - 进入文件夹 '{}' 处理内部文件".format(subifile_full))
                    if not os.path.isdir(subifile_full):
                        TUtilLog.info(
                            "不是文件夹 '{}' ".format(subifile_full))
                        continue
                    subi2 = os.listdir(subifile_full)
                    for subifile in subi2:
                        subifile_full2 = subifile_full + "/" + subifile
                        if copy_dir_m(subifile, subifile_full2, path):
                            continue
                        else:
                            TUtilLog.info(
                                "3 - 进入文件夹 '{}' 处理内部文件".format(subifile_full2))
                            if not os.path.isdir(subifile_full2):
                                TUtilLog.info(
                                    "不是文件夹 '{}' ".format(subifile_full2))
                                continue
                            subi3 = os.listdir(subifile_full2)
                            for subifile in subi3:
                                subifile_full3 = subifile_full2 + "/" + subifile
                                if copy_dir_m(subifile, subifile_full3, path):
                                    continue
                                else:
                                    TUtilLog.info(
                                        "4 - 进入文件夹 '{}' 处理内部文件".format(subifile_full3))
                                    if not os.path.isdir(subifile_full3):
                                        TUtilLog.info(
                                            "不是文件夹 '{}' ".format(subifile_full3))
                                        continue
                                    subi4 = os.listdir(
                                        subifile_full3)
                                    for subifile in subi4:
                                        subifile_full4 = subifile_full3 + "/" + subifile
                                        if copy_dir_m(subifile, subifile_full4, path):
                                            continue
                                        else:
                                            TUtilLog.info(
                                                "5 - 进入文件夹 '{}' 处理内部文件".format(subifile_full4))
                                            if not os.path.isdir(subifile_full4):
                                                TUtilLog.info(
                                                    "不是文件夹 '{}' ".format(subifile_full4))
                                                continue
                                            subi5 = os.listdir(
                                                subifile_full4)
                                            for subifile in subi5:
                                                subifile_full5 = subifile_full4 + "/" + subifile
                                                if copy_dir_m(subifile, subifile_full5, path):
                                                    continue
                                                else:
                                                    TUtilLog.info(
                                                        "6 - 进入文件夹 '{}' 处理内部文件".format(subifile_full5))
                                                    if not os.path.isdir(subifile_full5):
                                                        TUtilLog.info(
                                                            "不是文件夹 '{}' ".format(subifile_full5))
                                                        continue
                                                    subi6 = os.listdir(
                                                        subifile_full5)
                                                    for subifile in subi6:
                                                        subifile_full6 = subifile_full5 + "/" + subifile
                                                        if copy_dir_m(subifile, subifile_full6, path):
                                                            continue
                                                        else:
                                                            TUtilLog.warning(
                                                                "达到最深深度6，不再继续处理")
                                                            continue

def copy(src, tgp):
    shutil.copy(src, tgp)


def copy_dir(src_path, target_path):
    """
    复制文件 网上找的代码:))))))
    """
    global _install_completed
    if os.path.isdir(src_path) and os.path.isdir(target_path):
        filelist_src = os.listdir(src_path)
        for file in filelist_src:
            path = os.path.join(os.path.abspath(src_path), file)
            if os.path.isdir(path):
                path1 = os.path.join(os.path.abspath(target_path), file)
                if not os.path.exists(path1):
                    os.mkdir(path1)
                copy_dir(path, path1)
            else:
                with open(path, 'rb') as read_stream:
                    contents = read_stream.read()
                    path1 = os.path.join(target_path, file)
                    with open(path1, 'wb') as write_stream:
                        write_stream.write(contents)
        _install_completed = True
        return True
    else:
        return False


def copy_dir_m(dirs, file_name, path):
    """
    处理文件夹
    in:
        dirs - 文件夹,短名
        file_name - 文件夹绝对路径
        path - 根目录
    """
    TUtilLog.info("准备复制文件：'{}'".format(dirs))
    # bak_file_name =
    # if inseconddir == False:
    # files = os.listdir(file_name)
    # for dirs in files:
    if dirs == 'game':
        check_json(file_name + "/mod_assets", path)
        copy_dir(file_name, path + "/game")
        return True
    elif dirs == 'lib':
        copy_dir(file_name, path + "/lib")
        return True
    elif dirs == 'log':
        copy_dir(file_name, path + "/log")
        return True
    elif dirs == 'piano_songs':
        copy_dir(file_name, path + "/piano_songs")
        return True
    elif dirs == 'custom_bgm':
        copy_dir(file_name, path + "/custom_bgm")
        return True
    elif dirs == 'characters':
        TUtilLog.info("忽略该文件夹: '{}'".format(dirs))
        return True  # 什么都不做, 我不希望做一个一键解锁精灵包的东西--至少要手动移动文件.
    elif dirs == 'gift':
        TUtilLog.info("忽略该文件夹: '{}'".format(dirs))
        return True  # 什么都不做, 我不希望做一个一键解锁精灵包的东西--至少要手动移动文件.
    elif dirs == 'gifts':
        TUtilLog.info("忽略该文件夹: '{}'".format(dirs))
        return True  # 什么都不做, 我不希望做一个一键解锁精灵包的东西--至少要手动移动文件.
    # game下文件夹
    elif dirs == 'Submods':
        copy_dir(file_name, path + "/game/Submods")
        return True
    elif dirs == 'mod_assets':
        check_json(file_name, path)
        copy_dir(file_name, path + "/game/mod_assets")
        return True
    elif dirs == 'python-packages':
        copy_dir(file_name, path + "/game/python-packages")
        return True
    elif dirs == 'gui':
        copy_dir(file_name, path + "/game/gui")
        return True
    else:
        if os.path.isfile(file_name):
            if file_name in ['CustomIconMac.icns', 'CustomIconWindows.ico', 'README.html']:
                shutil.move(file_name, os.path.join(
                    path + "/"))
                return True
            if file_name.find('rpy') != -1:  # 如果是rpy文件
                if not os.path.exists(path + "/game/Submods/UnGroupScripts"):
                    os.mkdir(path + "/game/Submods/UnGroupScripts")
                shutil.move(file_name, os.path.join(
                    path + "/game/Submods/UnGroupScripts"))
                TUtilLog.warning(
                    "这是个脚本文件，复制到 'Submods/UnGroupScripts'：{}".format(file_name))
                return True
    TUtilLog.info("不符合任何常规子模组应有的文件夹： '{}'".format(file_name))
    return False


def check_json(filename, path, movedir=None):
    import json
    """
    用于检查json并生成gift文件
    vars:
        filename - mod_assets文件夹
        movedir - 失败后删除的文件夹
        path - 根目录
    """
    TUtilLog.info("检测精灵包json文件：'{}'".format(filename))
    if not os.path.exists(filename + "/monika/j"):
        TUtilLog.info("未找到的json文件夹，跳过检测礼物：'{}'".format(filename))
        return
    filename = filename + "/monika/j"
    files = os.listdir(filename)
    for jsonfile in files:
        if jsonfile.find('json') != -1:
            try:
                json_file = filename + "/" + jsonfile
                json_data = open(json_file).read()
                output_json = json.loads(json_data)
            except:
                # move_files(movedir,False)
                
                TUtilLog.error("在尝试读取 '{}' 出现异常，跳过".format(json_file))
                continue
            try:
                giftname = output_json['giftname']
                try:
                    gtype = "/" + output_json['select_info']['group'] + "/"
                except:
                    TUtilLog.warning(
                        "在尝试获取的礼物分组时出现异常，使用空分组： '{}' ".format(json_file))
                    gtype = "/"
                try:
                    if not os.path.exists(path + '/AvailableGift'):
                        os.mkdir(path + '/AvailableGift')
                    if not os.path.exists(path + '/AvailableGift' + gtype):
                        os.mkdir(path + '/AvailableGift' + gtype)
                    giftfile = open(path + '/AvailableGift' +
                                    gtype + giftname + '.gift', 'w')
                    giftfile.close()
                    TUtilLog.info("生成了礼物文件：'{}'".format(
                        'AvailableGift' + gtype + giftname + '.gift'))
                except Exception as e:
                    TUtilLog.error('生成礼物文件出现异常！{}'.format(e))
            except:
                TUtilLog.warning(
                    "在尝试获取礼物文件名时出现异常，可能未设置giftname，跳过该文件：'{}'".format(json_file))
                continue

def get_extra_file(data = None):
    # 下载额外内容仅在第一次安装时进行
    print_info("下载额外内容")
    if not data:
        # 主地址不通时依次尝试备用地址；无论走哪个，都要保证拿到的是 dict
        data = fetch_json([
            'https://raw.githubusercontent.com/Mon1-innovation/MAS-Simplified-Chinese-Patch/main/extra_file.json',
            'http://sp2.0721play.icu/d/MAS/MAS-PC/extra_file.json',
        ], "额外内容清单")
    if not isinstance(data, dict) or "extra_files" not in data:
        TUtilLog.error("额外内容清单格式异常，跳过：{}".format(data))
        return
    finished, skipped = 0, 0
    for file in tqdm(data["extra_files"], desc="额外内容"):
        name, url, dst, action = file[0], file[1], file[2], file[3]
        try:
            if action == "EXTRACT_EXTRA":
                download(url, dst, name)
                un_zip(dst + "/" + name)
                dir_check(dst + "/" + name, path = "./cache" + '/ddlc.zip_files/DDLC-1.1.1-pc')
            elif action == "ASK_DOWNLOAD":
                print_info("是否下载{}, 默认为N".format(name))
                if len(file) > 5 and file[5]:
                    print_info(file[5])
                try:
                    a = input().strip().lower()
                except EOFError:
                    # 静默/管道运行时没有输入，按“不下载”处理
                    a = ''
                if a != 'y':
                    print_info("取消下载")
                else:
                    download(url, dst, name)
            else:
                download(url, dst, name)
            finished += 1
        except Exception:
            # 额外内容只是说明文档和附加汉化，缺了不影响游戏本体，绝不能因此中断整个安装
            skipped += 1
            TUtilLog.warning("额外内容 '{}' 处理失败，已跳过：\n{}".format(name, traceback.format_exc()))
            print_info("额外内容 '{}' 处理失败，已跳过".format(name))
    if skipped:
        print_info("额外内容完成 {} 个，跳过 {} 个（不影响游戏本体）".format(finished, skipped))

