from PriceMonitor.crawler_selenium import Crawler
import time
import json
import datetime
import re
import concurrent.futures
import requests

WECHAT_PAGE = "pages/index/index"  # 跳转页面，可按需修改

def get_wechat_config():
    """
    读取 monitor_items.json 的 wechat 配置，根据 mode 选择订阅消息或模板消息参数。
    返回 (appid, secret, template_id, openid, mode)
    """
    try:
        with open("monitor_items.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            wechat = config.get("wechat", {})
            mode = wechat.get("mode", "subscribe")
            if mode == "template":
                sub = wechat.get("template_message", {})
            else:
                sub = wechat.get("subscribe_message", {})
            return (
                sub.get("appid", ""),
                sub.get("secret", ""),
                sub.get("template_id", ""),
                sub.get("openid", ""),
                mode
            )
    except Exception as e:
        print(f"读取微信配置失败: {e}")
        return ("", "", "", "", "subscribe")

def get_wechat_access_token(appid, secret):
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get("access_token")
    except Exception as e:
        print(f"获取微信 access_token 失败: {e}")
        return None

def send_wechat_message(openid, template_id, page, data, access_token, mode="subscribe"):
    """
    mode: "subscribe"(默认) 走订阅消息接口，"template"走模板消息接口
    """
    if mode == "template":
        url = f"https://api.weixin.qq.com/cgi-bin/message/wxopen/template/send?access_token={access_token}"
        payload = {
            "touser": openid,
            "template_id": template_id,
            "page": page,
            "form_id": "FORM_ID",  # 模板消息需要form_id，实际使用需传入
            "data": data
        }
    else:
        url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={access_token}"
        payload = {
            "touser": openid,
            "template_id": template_id,
            "page": page,
            "data": data
        }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"发送微信消息失败: {e}")
        return None

# 新增：独立测试订阅消息推送的函数
def send_test_wechat_subscribe_message():
    WECHAT_APPID, WECHAT_SECRET, WECHAT_TEMPLATE_ID, WECHAT_OPENID, WECHAT_MODE = get_wechat_config()
    if not all([WECHAT_APPID, WECHAT_SECRET, WECHAT_TEMPLATE_ID, WECHAT_OPENID]):
        print("请确保 appid、secret、template_id、openid 均已正确填写！")
        return
    access_token = get_wechat_access_token(WECHAT_APPID, WECHAT_SECRET)
    if not access_token:
        print("获取 access_token 失败")
        return
    # 按你的新模板字段发送（thing1: 备忘标题, thing2: 备忘内容）
    data = {
        "thing1": {"value": "价格变化备忘"},
        "thing2": {"value": "价格降至5799元"}  # 内容简化，避免超长和特殊字符
    }
    result = send_wechat_message(
        WECHAT_OPENID, WECHAT_TEMPLATE_ID, WECHAT_PAGE, data, access_token, WECHAT_MODE
    )
    print(f"[微信订阅消息] 推送结果: {result}")

def test_with_saved_cookies():
    """使用已保存的 cookies 测试商品价格获取"""
    crawler = Crawler()  # 获取或创建实例
    # 测试商品 ID
    item_id = "100038005189"  # 可以替换为其他商品 ID
    try:
        print("\n使用已保存的 cookies 获取商品信息...")
        # 获取商品信息
        item_info = crawler.get_jd_item(item_id)
        print("\n商品信息：")
        print(f"名称: {item_info['name']}")
        print(f"价格: {item_info['price']}")
        print(f"PLUS价格: {item_info['plus_price']}")
        print(f"副标题: {item_info['subtitle']}")
        
    except Exception as e:
        print(f"发生错误: {e}")


def test_with_saved_cookies_monitor():
    """使用已保存的 cookies 持续监控商品列表价格，每分钟获取一次，失败自动停止"""
    import json
    # 从配置文件读取商品详情页 url 列表
    with open("monitor_items.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        item_urls = config.get("items", [])
        interval = config.get("interval", 60)
    print(f"\n开始监控商品列表价格，每 {interval} 秒采集一次...")
    crawler = Crawler()
    while True:
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for url in item_urls:
            try:
                item_info = crawler.get_jd_item(url)
                not_found = item_info['price'] is None
                # 获取页面标题
                if hasattr(crawler, 'chrome') and crawler.chrome:
                    title = crawler.chrome.title if not_found else item_info.get('name') or crawler.chrome.title
                else:
                    title = '没有找到'
                if not_found:
                    title = '没有找到'
                on_price_checked(url, item_info['price'], not_found, title)
                print(f"[{now_str}] {url} 价格: {item_info['price']} 元")
            except Exception as e:
                print(f"[{now_str}] {url} 获取价格失败，跳过: {e}")
                continue
        time.sleep(interval)


def wait_for_login():
    """等待用户登录并保存 cookies"""
    crawler = Crawler()  # 获取或创建实例
    print("\n1. 打开登录页面...")
    crawler.chrome.get('https://passport.jd.com/new/login.aspx')
    while True:
        print("\n请选择操作：")
        print("1. 我已完成登录，保存 cookies")
        print("2. 检查登录状态")
        print("3. 退出")
        choice = input("\n请输入选项（1-3）: ")
        if choice == "1":
            if "请登录" in crawler.chrome.page_source:
                print("\n似乎还没有登录成功，请先完成登录")
                continue
            cookies = crawler.chrome.get_cookies()
            if cookies:
                print("\n当前的 cookies:")
                for cookie in cookies:
                    print(json.dumps(cookie, ensure_ascii=False, indent=2))
                crawler.save_cookies()
                print("\nCookies 已保存到文件")
                return True
            else:
                print("\n未找到任何 cookies")
        elif choice == "2":
            if "请登录" not in crawler.chrome.page_source:
                print("\n已经登录")
            else:
                print("\n尚未登录")
        elif choice == "3":
            print("\n退出操作")
            return False
        else:
            print("\n无效的选项，请重试")


def test_jd_price():
    """测试获取商品价格"""
    crawler = Crawler()  # 获取或创建实例
    # 测试商品 ID
    item_id = "100038005189"  # 可以替换为其他商品 ID
    try:
        # 获取商品信息
        item_info = crawler.get_jd_item(item_id)
        print("\n商品信息：")
        print(f"名称: {item_info['name']}")
        print(f"价格: {item_info['price']}")
        print(f"PLUS价格: {item_info['plus_price']}")
        print(f"副标题: {item_info['subtitle']}")
        
    except Exception as e:
        print(f"发生错误: {e}")


def on_price_checked(url, price, not_found, title):
    """
    价格检查回调。
    url: 商品链接
    price: 价格字符串或 None
    not_found: bool，True 表示未找到价格，False 表示已找到价格
    title: 页面标题，未找到价格时为 '没有找到'
    """
    WECHAT_APPID, WECHAT_SECRET, WECHAT_TEMPLATE_ID, WECHAT_OPENID, WECHAT_MODE = get_wechat_config()
    if not_found:
        print(f"[回调] {url} 未找到价格，页面标题: {title}")
        # 发送微信消息通知（价格未找到提醒）
        access_token = get_wechat_access_token(WECHAT_APPID, WECHAT_SECRET)
        if access_token:
            data = {
                # 根据你的小程序模板字段调整
                "thing1": {"value": title or "未找到"},
                "thing2": {"value": "未找到价格"},
                "thing3": {"value": url}
            }
            result = send_wechat_message(
                WECHAT_OPENID, WECHAT_TEMPLATE_ID, WECHAT_PAGE, data, access_token, WECHAT_MODE
            )
            print(f"[微信消息] 未找到价格，发送结果: {result}")
        else:
            print("[微信消息] 获取 access_token 失败，未发送")
    else:
        print(f"[回调] {url} 价格: {price} 元，页面标题: {title}")
        # 发送微信消息通知（价格正常提醒）
        access_token = get_wechat_access_token(WECHAT_APPID, WECHAT_SECRET)
        if access_token:
            data = {
                # 根据你的小程序模板字段调整
                "thing1": {"value": title or ""},
                "amount2": {"value": str(price)},
                "thing3": {"value": url}
            }
            result = send_wechat_message(
                WECHAT_OPENID, WECHAT_TEMPLATE_ID, WECHAT_PAGE, data, access_token, WECHAT_MODE
            )
            print(f"[微信消息] 价格提醒，发送结果: {result}")
        else:
            print("[微信消息] 获取 access_token 失败，未发送")


if __name__ == "__main__":
    print("欢迎使用京东商品信息获取工具")
    print("=" * 50)
    print("\n请选择操作：")
    print("1. 登录并保存新的 cookies")
    print("2. 使用已保存的 cookies 监控价格")
    print("3. 测试订阅消息推送")
    print("4. 退出")
    choice = input("\n请输入选项（1-4）: ")
    if choice == "1":
        if wait_for_login():
            print("\n现在测试使用新保存的 cookies...")
            test_with_saved_cookies_monitor()
    elif choice == "2":
        test_with_saved_cookies_monitor()
    elif choice == "3":
        send_test_wechat_subscribe_message()
    else:
        print("\n操作已取消")
