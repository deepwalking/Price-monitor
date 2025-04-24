from PriceMonitor.crawler_selenium import Crawler
import time
import json
import datetime
import re
import concurrent.futures
import os
import pickle

def monitor():
    """使用已保存的 cookies 持续监控商品列表价格，每分钟获取一次，失败自动停止"""
    # 创建一个新的爬虫实例，但不加载cookies
    crawler = Crawler(skip_cookies=True)
    
    cookie_file = "jd_pc_cookies.pkl"
    
    # 检查cookie文件是否存在
    if not os.path.exists(cookie_file):
        print(f"\n未找到有效的cookie文件 {cookie_file}，请先登录并保存cookie")
        return False
    
    # 尝试读取cookies
    all_cookies = []
    print(f"\n尝试读取cookies {cookie_file}...")
    try:
        with open(cookie_file, 'rb') as f:
            cookies = pickle.load(f)
            if cookies:
                all_cookies.extend(cookies)
            else:
                print("cookie文件存在但没有内容")
    except Exception as e:
        print(f"读取cookies失败: {e}")
        return False
    
    # 检查是否成功加载了cookie
    if not all_cookies:
        print("\n未找到有效的cookies，请先登录并保存cookies")
        crawler.quit()
        return False
    
    # 先访问京东主页
    crawler.chrome.get('https://www.jd.com')
    time.sleep(1)
    
    # 添加所有cookie
    for cookie in all_cookies:
        try:
            # 确保cookie有效
            if 'expiry' in cookie and cookie['expiry'] < time.time():
                continue
            crawler.chrome.add_cookie(cookie)
        except Exception as e:
            continue
    
    # 刷新页面以应用cookies
    crawler.chrome.refresh()
    time.sleep(1)
    
    # 验证登录状态
    if not crawler.check_login_status():
        print("\ncookie已失效，请重新登录")
        crawler.quit()
        return False
    else:
        print("\n已成功使用cookies登录京东")
    
    # 读取监控列表和间隔
    try:
        with open("monitor_items.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            items = config.get("items", [])
            interval = config.get("interval", 60)  # 默认60秒
    except Exception as e:
        print(f"读取监控配置失败: {e}")
        return False
    
    if not items:
        print("监控列表为空，请先添加商品")
        return False
    
    print(f"\n开始监控商品列表价格，每 {interval} 秒采集一次...")
    
    while True:
        for url in items:
            try:
                print(f"\n正在访问商品: {url}")
                item_info = crawler.get_jd_item(url)
                price = item_info['price']
                title = item_info['name']
                
                if price:
                    call_rpc(url, price, False, title)
                else:
                    print(f"[{now_str}] {url} 未找到价格")
            except Exception as e:
                now = datetime.datetime.now()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now_str}] {url} 获取价格失败，跳过: {e}")
                continue
        time.sleep(interval)


def wait_for_login():
    """等待用户登录并保存 cookies"""
    # cookie文件名
    cookie_file = "jd_pc_cookies.pkl"
    
    # 创建不加载cookies的爬虫实例
    crawler = Crawler(skip_cookies=True, cookies_file=cookie_file)  # 获取或创建实例，但不加载cookies
    
    print("\n1. 打开登录页面...")
    crawler.chrome.get('https://passport.jd.com/new/login.aspx')
    print("\n请在浏览器中完成登录，登录成功后按回车键继续...")
    
    input()
    
    # 检查登录状态
    if "请登录" in crawler.chrome.page_source:
        print("\n似乎还没有登录成功，请重新选择操作")
        # 确保关闭浏览器
        crawler.quit()
        return False
        
    cookies = crawler.chrome.get_cookies()
    if cookies:
        print(f"\n检测到登录成功！正在保存cookies到 {cookie_file}...")
        saved = crawler.save_cookies()
        if saved:
            print(f"\nCookies 已成功保存到文件 {cookie_file}")
        else:
            print("\nCookies 保存失败")
        
        # 关闭浏览器，避免资源占用
        crawler.quit()
        return saved
    else:
        print("\n未找到任何 cookies，登录可能失败")
        # 确保关闭浏览器
        crawler.quit()
        return False


def call_rpc(url, price, not_found, title):
    """
    价格检查回调。
    url: 商品链接
    price: 价格字符串或 None
    not_found: bool，True 表示未找到价格，False 表示已找到价格
    title: 页面标题，未找到价格时为 '没有找到'
    """
    if not_found:
        print(f"[回调] {url} 未找到价格，页面标题: {title}")
    else:
        print(f"[回调] {url} 价格: {price} 元，页面标题: {title}")


if __name__ == "__main__":
    crawler = None
    try:
        while True:
            print("欢迎使用京东商品信息获取工具")
            print("=" * 50)
            print("\n请选择操作：")
            print("1. 登录并保存COOKIE")
            print("2. 监控价格")
            print("3. 退出")
            choice = input("\n请输入选项（1-3）: ")
            
            if choice == "1":
                login_result = wait_for_login()
                if login_result:
                    print("\n登录成功并已保存COOKIE")
                else:
                    print("\n登录或保存COOKIE失败")
                input("\n按回车键返回主菜单...")
                
            elif choice == "2":
                try:
                    monitor()
                except KeyboardInterrupt:
                    print("\n监控被用户中断")
                except Exception as e:
                    print(f"\n监控出错: {e}")
                input("\n按回车键返回主菜单...")
                
            elif choice == "3" or choice.lower() == "q":
                print("\n感谢使用，再见！")
                break
                
            else:
                print("\n无效的选项，请重新选择")
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n程序被用户中断，正在退出...")
    finally:
        # 确保所有浏览器实例都被关闭
        try:
            if crawler is not None:
                crawler.quit()
            # 尝试关闭任何可能仍在运行的Chrome实例
            from selenium import webdriver
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')  # 无头模式，不显示浏览器窗口
            temp_driver = webdriver.Chrome(options=options)
            temp_driver.quit()
        except:
            pass  # 忽略关闭浏览器时的任何错误
        # 强制结束程序，确保没有浏览器进程残留
        import os
        import signal
        os._exit(0)  # 立即终止程序，不执行任何清理操作
