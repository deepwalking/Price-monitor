from PriceMonitor.crawler_selenium import Crawler
import time
import json
import datetime


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
    """使用已保存的 cookies 持续监控商品价格，每分钟获取一次，失败或超6小时自动停止"""
    crawler = Crawler()  # 获取或创建实例
    item_id = "100038005189"  # 可替换为其他商品 ID
    start_time = time.time()
    max_seconds = 6 * 60 * 60  # 6小时
    print(f"\n开始监控商品价格，最多持续6小时，每分钟采集一次...")
    while True:
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            item_info = crawler.get_jd_item(item_id)
            print(f"[{now_str}] 商品价格: {item_info['price']} 元")
        except Exception as e:
            print(f"[{now_str}] 获取价格失败，程序停止: {e}")
            return
        # 检查是否超时
        elapsed = time.time() - start_time
        if elapsed >= max_seconds:
            print(f"[{now_str}] 已持续运行6小时，监控结束。最后一次价格: {item_info['price']} 元")
            return
        time.sleep(60)


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


if __name__ == "__main__":
    print("欢迎使用京东商品信息获取工具")
    print("=" * 50)
    print("\n请选择操作：")
    print("1. 登录并保存新的 cookies")
    print("2. 使用已保存的 cookies 监控价格")
    print("3. 使用已保存的 cookies 测试")
    print("4. 测试获取商品价格")
    print("5. 退出")
    choice = input("\n请输入选项（1-5）: ")
    if choice == "1":
        if wait_for_login():
            print("\n现在测试使用新保存的 cookies...")
            test_with_saved_cookies_monitor()
    elif choice == "2":
        test_with_saved_cookies_monitor()
    elif choice == "3":
        test_with_saved_cookies()
    elif choice == "4":
        test_jd_price()
    else:
        print("\n操作已取消")
