from PriceMonitor.crawler_selenium import Crawler
import time
import json
import datetime
import re
import concurrent.futures
import os
import pickle

LAST_MONITOR_STATUS_FILE = "last_monitor_status.json"

def load_monitor_status():
    try:
        with open(LAST_MONITOR_STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            last_prices = data.get("last_prices", {})
            last_coupon_status = data.get("last_coupon_status", {})
            return last_prices, last_coupon_status
    except Exception:
        return {}, {}

def save_last_prices(last_prices):
    try:
        data = {}
        if os.path.exists(LAST_MONITOR_STATUS_FILE):
            with open(LAST_MONITOR_STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["last_prices"] = last_prices
        with open(LAST_MONITOR_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存last_prices失败: {e}")

def save_last_coupon_status(last_coupon_status):
    try:
        data = {}
        if os.path.exists(LAST_MONITOR_STATUS_FILE):
            with open(LAST_MONITOR_STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["last_coupon_status"] = last_coupon_status
        with open(LAST_MONITOR_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存last_coupon_status失败: {e}")

def monitor():
    """使用已保存的 cookies 持续监控商品列表价格，每分钟获取一次，失败自动停止"""
    # 创建一个新的爬虫实例，但不加载cookies
    crawler = Crawler(skip_cookies=True)
    
    # 用于存储每个商品的上次价格，用于检测价格变化
    last_prices, last_coupon_status = load_monitor_status()
    
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
                title = item_info['title']
                if title == "" or title is None:
                    print(f"\n商品 {url} 未找到标题，跳过")
                    send_jd_exception_notice("商品 {url} 标题未找到")
                    continue
                if price == "" or price is None:
                    print(f"\n商品 {url} 未找到价格，跳过")
                    send_jd_exception_notice("商品 {url} 价格未找到")
                    continue
                has_coupon = item_info['has_coupon']
                coupon_detail_list = item_info['coupon_detail_list']
                
                if has_coupon:
                    # 检查优惠券状态变化（新增或内容变化才推送）
                    if (url not in last_coupon_status or
                        last_coupon_status[url]['coupon_detail_list'] != coupon_detail_list):
                        print(f"准备推送优惠券变化通知: {url}, {title}")
                        send_jd_coupon_notice(url, title)
                        last_coupon_status[url] = {
                            'has_coupon': has_coupon,
                            'coupon_detail_list': coupon_detail_list
                        }
                        save_last_coupon_status(last_coupon_status)

                if price:
                    # 检查是否有价格变化

                    # 如果商品之前已经监控过（非第一次）
                    if url in last_prices:
                        # 如果价格发生了变化
                        if last_prices[url] != price:
                            # 创建价格变化状态信息
                            old_price = last_prices[url]
                            new_price = price
                            
                            # 比较价格变化方向
                            if float(new_price) > float(old_price):
                                change_direction = "上涨"
                            else:
                                change_direction = "下降"
                            # 这里可以推送价格变化通知等...
                            # 格式化status信息
                            status = f"{change_direction}，原价格：{old_price}"
                            print(f"价格变化！{url} 价格从 {old_price} 变为 {new_price}，{status}, 准备推送价格变化通知.")
                            send_jd_price_change_notice(url, price, title, status)
                            
                            last_prices[url] = price
                            save_last_prices(last_prices)
                        # 如果价格没变，不做处理
                    else:
                        # 第一次检测也发送通知，状态为"初始化"
                        status = f"初始采集价格：{price}"
                        print(f"首次监控 {url}，价格: {price} 元，{status}, 准备推送价格变化通知.")
                        send_jd_price_change_notice(url, price, title, status)
                        
                        # 第一次监控该商品，直接记录
                        last_prices[url] = price
                        save_last_prices(last_prices)
                else:
                    now = datetime.datetime.now()
                    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{now_str}] {url} 未找到价格")
            except Exception as e:
                now = datetime.datetime.now()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now_str}] {url} 获取商品信息异常，跳过: {e}")
                send_jd_exception_notice(f"{now_str}, {url}, 获取商品信息异常: {e}")
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


def send_jd_price_change_notice(url, price, title, status):
    try:
        import re
        match = re.search(r'/(\d+)\.html', url)
        if not match:
            print(f"无法从URL中提取商品ID: {url}")
            return
            
        product_id = match.group(1)
        
        title_short = title[:20]
        
        payload = {
            "price": price,
            "id": product_id,
            "title": title_short,
            "status": status
        }
        
        print(f"发送价格变化通知: {payload}")
        
        import requests
        api_url = "https://api.azzjia.com/common/SendJdPriceChangeNotice"
        response = requests.post(api_url, json=payload, timeout=5)
        print(f"价格变化通知发送结果: {response.status_code}")
            
    except Exception as e:
        print(f"处理价格变化通知时出错: {e}")


def send_jd_coupon_notice(url, title):
    try:
        import re
        match = re.search(r'/(\d+)\.html', url)
        if not match:
            print(f"无法从URL中提取商品ID: {url}")
            return
            
        product_id = match.group(1)
        
        title_short = title[:20]
        
        payload = {
            "id": product_id,
            "title": title_short,
        }
        
        print(f"发送优惠券变化通知: {payload}")
        
        import requests
        api_url = "https://api.azzjia.com/common/SendJdCouponNotice"
        response = requests.post(api_url, json=payload, timeout=5)
        print(f"发送优惠券通知发送结果: {response.status_code}")
            
    except Exception as e:
        print(f"处理优惠券变化通知时出错: {e}")


def send_jd_exception_notice(exceiption):
    try:
        payload = {
            "exception": exceiption,
        }
        
        print(f"发送异常通知: 异常类型: {exceiption}")
        
        import requests
        api_url = "https://api.azzjia.com/common/SendJdExceptionNotice"
        response = requests.post(api_url, json=payload, timeout=5)
        print(f"发送异常通知发送结果: {response.status_code}")
            
    except Exception as e:
        print(f"处理异常通知时出错: {e}")

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
                # 监控价格
                last_prices, last_coupon_status = load_monitor_status()
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
