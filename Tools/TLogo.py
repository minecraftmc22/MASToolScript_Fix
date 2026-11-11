import os

# 当前版本；发版时改这里，并打同名 tag（如 v0.0.15），CI 会校验两者一致
VER = "0.0.15"
# 维护者：Minecraftmc22（原版 by Sir.P）
MAINTAINER = "Minecraftmc22"
REPO_OWNER = "minecraftmc22"
REPO_NAME = "MASToolScript_Fix"
REPO_URL = "https://github.com/{}/{}".format(REPO_OWNER, REPO_NAME)

# 注意：必须在上面这些常量之后导入。TUtilLog 初始化时会读取 TLogo.VER，
# 提前导入会触发循环导入（TLogo -> TUtil -> TUtilLog -> TLogo）。
import TUtil
MOYU = R"""

          _____                   _______               _____                    _____
         /\    \                 /::\    \             |\    \                  /\    \
        /::\____\               /::::\    \            |:\____\                /::\____\
       /::::|   |              /::::::\    \           |::|   |               /:::/    /
      /:::::|   |             /::::::::\    \          |::|   |              /:::/    /
     /::::::|   |            /:::/~~\:::\    \         |::|   |             /:::/    /
    /:::/|::|   |           /:::/    \:::\    \        |::|   |            /:::/    /
   /:::/ |::|   |          /:::/    / \:::\    \       |::|   |           /:::/    /
  /:::/  |::|___|______   /:::/____/   \:::\____\      |::|___|______    /:::/    /      _____
 /:::/   |::::::::\    \ |:::|    |     |:::|    |     /::::::::\    \  /:::/____/      /\    \
/:::/    |:::::::::\____\|:::|____|     |:::|    |    /::::::::::\____\|:::|    /      /::\____\
\::/    / ~~~~~/:::/    / \:::\    \   /:::/    /    /:::/~~~~/~~      |:::|____\     /:::/    /
 \/____/      /:::/    /   \:::\    \ /:::/    /    /:::/    /          \:::\    \   /:::/    /
             /:::/    /     \:::\    /:::/    /    /:::/    /            \:::\    \ /:::/    /
            /:::/    /       \:::\__/:::/    /    /:::/    /              \:::\    /:::/    /
           /:::/    /         \::::::::/    /     \::/    /                \:::\__/:::/    /
          /:::/    /           \::::::/    /       \/____/                  \::::::::/    /
         /:::/    /             \::::/    /                                  \::::::/    /
        /:::/    /               \::/____/                                    \::::/    /
        \::/    /                 ~~                                           \::/____/
         \/____/                                                                ~~


----------------------------------------------------------------------------------------
欢迎使用 MASToolKit by {} v{}
当提示选项时，输入对应的选项，然后按下回车键确定选项。
如果程序卡住，可以尝试点一下回车来继续。（通常这种情况发生时，标题栏会出现“选择”二字）
本程序一般不需要加速器，开启加速器可能会导致异常
----------------------------------------------------------------------------------------
Monika After Story本次安装的目标位置由本可执行文件所在的位置决定。
目标位置：{}
""".format(MAINTAINER, VER, os.path.abspath('.'))

QA = """
1. 异常 "ValueError: check_hostname requires server_hostname"

A: 关闭梯子


2. 异常中出现关键词 "[SSL: CERTIFICATE_VERIFY_FAILED]" "requests.exceptions.SSLError" 
完整：requests.exceptions.SSLError: HTTPSConnectionPool(host='api.github.com', port=443): Max retries exceeded with url: /repos/minecraftmc22/MASToolScript_Fix/releases/latest (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1129)')))

A: 关闭Steam++ / Watt Toolkit / 梯子


3. 出现意义不明的异常

A: 发送MASToolKit.log到Discord/QQ/Github issue等地寻求帮助
Github issue：{}/issues


4. 提示"获取 MAS 最新版本失败"，或旧版本直接报 "IndexError: list index out of range"

A: 说明没能从 Github 接口读到 release 信息，常见原因是网络被拦截、触发了接口限额
   （未登录时 60 次/小时），或仓库接口临时异常。
   先关闭梯子 / Steam++ / Watt Toolkit 再试；仍失败就等几分钟重试。
   新版遇到这种情况会给出提示并退出，不会再把已下载的缓存清掉。


""".format(REPO_URL)

def moyu():
    print(MOYU)
    out_files()
    new_ver = self_checkupdate()
    try:
        if new_ver:
            print("MASToolKit 有新版本：{} -> {}".format(VER, new_ver))
            print("====================================")
            print(TUtil.get_latest_release_info(REPO_OWNER, REPO_NAME))
            print("你可以在 {}/releases/latest 更新 MASToolKit".format(REPO_URL))
            print("====================================")
    except:
        pass
        

def self_checkupdate():
    try:
        return TUtil.check_update(VER.split('.'), REPO_OWNER, REPO_NAME)
    except:
        return False


def out_files():
    try:
        with open("MASToolKit常见问题QA.txt", 'w', encoding='utf-8') as a:
            a.write(QA)
    except OSError as e:
        print("写入常见问题文件失败：{}".format(e))
    