from PriceMonitor.crawler_selenium import Crawler
import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def test_jd_price():
    logging.basicConfig(level=logging.INFO)
    crawler = Crawler()
    
    # 先访问登录页面
    print("正在打开登录页面...")
    crawler.chrome.get('https://passport.jd.com/new/login.aspx')
    
    # 等待用户手动登录
    print("\n请在浏览器中手动完成登录...")
    print("程序将等待直到检测到登录成功...")
    
    # 等待登录成功（通过检查是否存在用户信息元素）
    try:
        WebDriverWait(crawler.chrome, 300).until(
            lambda driver: driver.current_url.startswith('https://www.jd.com')
        )
        print("登录成功！")
    except Exception as e:
        print("等待登录超时，请在5分钟内完成登录")
        crawler.chrome.quit()
        return
    
    # 访问商品页面
    jd_item_id = '10145225792900'
    print(f"\n正在获取商品 {jd_item_id} 的信息...")
    item_info = crawler.get_jd_item(jd_item_id)
    
    # 打印商品信息
    print("\n商品信息：")
    print(f"名称: {item_info['name']}")
    print(f"价格: {item_info['price']}")
    print(f"Plus价格: {item_info['plus_price']}")
    print(f"副标题: {item_info['subtitle']}")

if __name__ == '__main__':
    test_jd_price()
