#!/usr/bin/env python3
# coding=utf-8
import re
import logging
from json import decoder
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import random
import os
import pickle


class Crawler(object):
    _instance = None
    _chrome = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, proxy=None):
        # 如果已经初始化过，直接返回
        if self._chrome is not None:
            return
            
        chrome_options = Options()
        
        # 添加反检测参数
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 性能优化设置
        chrome_options.add_argument('--disable-gpu')  # 禁用 GPU 加速
        chrome_options.add_argument('--no-sandbox')  # 禁用沙箱模式
        chrome_options.add_argument('--disable-dev-shm-usage')  # 禁用共享内存
        chrome_options.add_argument('--disable-infobars')  # 禁用信息栏
        chrome_options.add_argument('--disable-notifications')  # 禁用通知
        chrome_options.add_argument('--disable-popup-blocking')  # 允许弹出窗口
        chrome_options.add_argument('--disable-extensions')  # 禁用扩展
        chrome_options.add_argument('--disable-logging')  # 禁用日志
        chrome_options.add_argument('--disable-default-apps')  # 禁用默认应用
        chrome_options.add_argument('--disable-background-timer-throttling')  # 禁用后台计时器限制
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')  # 禁用后台窗口限制
        chrome_options.add_argument('--disable-renderer-backgrounding')  # 禁用渲染器后台处理
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')  # 禁用站点隔离
        chrome_options.add_argument('--ignore-certificate-errors')  # 忽略证书错误
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.7049.95 Safari/537.36')
        
        if proxy:
            proxy_address = proxy['https']
            chrome_options.add_argument('--proxy-server=%s' % proxy_address)
            logging.info('Chrome using proxy: %s', proxy['https'])
        
        service = Service('/usr/local/bin/chromedriver')
        self._chrome = webdriver.Chrome(service=service, options=chrome_options)
        
        # 执行 JavaScript 来修改 WebDriver 特征
        self._chrome.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
                window.navigator.chrome = {
                    runtime: {},
                };
                
                // 清除 automation controller
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                
                // 修改 webdriver 属性
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false
                });
            '''
        })
        
        # 设置窗口大小为较小的尺寸，以减少资源占用
        self._chrome.set_window_size(1366, 768)
        # 设置较短的超时时间
        self._chrome.set_page_load_timeout(20)
        self._chrome.set_script_timeout(20)
        self._chrome.implicitly_wait(5)
        
        # 尝试加载已保存的 cookies
        self.cookies_file = 'jd_cookies.pkl'
        self.load_cookies()

    @property
    def chrome(self):
        return self._chrome

    def quit(self):
        """安全关闭浏览器"""
        if self._chrome is not None:
            try:
                self._chrome.quit()
            except Exception as e:
                print(f"关闭浏览器时发生错误: {e}")
            finally:
                self._chrome = None
                Crawler._instance = None

    def __del__(self):
        """析构函数，确保浏览器被关闭"""
        self.quit()

    def save_cookies(self):
        """保存 cookies 到文件"""
        try:
            cookies = self.chrome.get_cookies()
            if cookies:
                with open(self.cookies_file, 'wb') as f:
                    pickle.dump(cookies, f)
                    print("Cookies 已保存")
                return True
        except Exception as e:
            print(f"保存 cookies 失败: {e}")
        return False

    def load_cookies(self):
        """从文件加载 cookies"""
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, 'rb') as f:
                    cookies = pickle.load(f)
                    if cookies:
                        # 先访问一下京东主页，这样才能添加 cookies
                        self.chrome.get('https://www.jd.com')
                        time.sleep(1)
                        
                        # 添加所有 cookies
                        for cookie in cookies:
                            try:
                                # 确保 cookie 有效
                                if 'expiry' in cookie:
                                    # 转换为整数
                                    cookie['expiry'] = int(cookie['expiry'])
                                self.chrome.add_cookie(cookie)
                            except Exception as e:
                                print(f"添加单个 cookie 失败: {e}")
                                continue
                        
                        print("Cookies 已加载")
                        # 刷新页面以应用 cookies
                        self.chrome.refresh()
                        time.sleep(1)
                        
                        # 验证登录状态
                        if self.check_login_status():
                            print("Cookies 有效，已成功登录")
                            return True
                        else:
                            print("Cookies 已失效")
                            # 删除失效的 cookies 文件
                            os.remove(self.cookies_file)
        except Exception as e:
            print(f"加载 cookies 失败: {e}")
        return False

    def check_login_status(self):
        """检查是否已登录"""
        try:
            self.chrome.get('https://www.jd.com')
            time.sleep(1)
            
            # 检查多个可能的未登录标识
            not_logged_in_indicators = [
                "请登录",
                "登录注册",
                "login-tab-r",
                "登录京东"
            ]
            
            page_source = self.chrome.page_source
            for indicator in not_logged_in_indicators:
                if indicator in page_source:
                    return False
                    
            # 尝试检查登录后才会出现的元素
            try:
                # 等待可能出现的用户名元素
                WebDriverWait(self.chrome, 3).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "nickname"))
                )
                return True
            except:
                pass
                
            return True
            
        except Exception as e:
            print(f"检查登录状态失败: {e}")
            return False

    def login(self):
        """处理登录流程"""
        print("\n需要登录，请在打开的浏览器窗口中完成登录...")
        self.chrome.get('https://passport.jd.com/new/login.aspx')
        print("等待用户登录...")
        print("登录后请按回车键继续...")
        input()
        
        # 检查登录状态
        if self.check_login_status():
            print("登录成功！")
            self.save_cookies()
            return True
        else:
            print("登录失败或未完成登录")
            return False

    def _find_element_safe(self, by, value):
        """安全地查找元素，如果找不到返回 None"""
        try:
            return self.chrome.find_element(by, value)
        except NoSuchElementException:
            return None
            
    def get_jd_item(self, item_id):
        item_info_dict = {"name": None, "price": None, "plus_price": None, "subtitle": None}
        original_url = None  # 保存登录前的商品URL
        
        try:
            # 构建商品URL
            url = 'https://item.jd.com/' + item_id + '.html'
            original_url = url  # 保存URL以便登录后返回
            
            # 先尝试直接访问商品页面
            print(f"\n正在访问商品页面: {url}")
            self.chrome.get(url)
            time.sleep(2)
            
            # 检查是否需要登录
            if not self.check_login_status():
                print("需要登录")
                if self.login():
                    # 登录成功后，重新访问商品页面
                    print(f"\n重新访问商品页面: {original_url}")
                    self.chrome.get(original_url)
                    time.sleep(2)
                else:
                    print("登录失败，继续尝试获取商品信息")
            
            # 确保页面加载到了正确的商品页面
            retry_count = 0
            while retry_count < 3 and (item_id not in self.chrome.current_url):
                print(f"页面未正确加载（当前URL: {self.chrome.current_url}），第{retry_count + 1}次重试...")
                self.chrome.get(url)
                time.sleep(2 + retry_count)  # 每次重试增加等待时间
                retry_count += 1
            
            if item_id not in self.chrome.current_url:
                print("无法加载商品页面，可能是商品不存在")
                return item_info_dict
            
            # 等待商品信息加载
            try:
                # 等待商品名称元素出现
                WebDriverWait(self.chrome, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "sku-name"))
                )
                
                # 执行滚动以确保所有元素加载
                self.chrome.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                
                # 获取商品信息
                self._extract_item_info(item_info_dict)
                
            except TimeoutException:
                print("等待商品信息加载超时")
            
        except Exception as e:
            logging.warning('Crawl failure: {}'.format(e))
            print(f"发生错误: {str(e)}")
        finally:
            if any(value is not None for value in item_info_dict.values()):
                # 只有在成功获取到信息时才保存 cookies
                self.save_cookies()
            logging.info('Crawl finished: {}'.format(item_info_dict))
            
        return item_info_dict

    def _extract_item_info(self, item_info_dict):
        """提取商品信息的内部方法"""
        # 提取商品名称
        try:
            selectors = [
                "//div[@class='sku-name']",
                "//div[contains(@class, 'item-name')]",
                "//div[contains(@class, 'product-intro')]//div[@class='name']"
            ]
            for selector in selectors:
                element = self._find_element_safe(By.XPATH, selector)
                if element and element.text:
                    item_info_dict['name'] = element.text
                    break
        except Exception as e:
            logging.warning('Crawl name failure: {}'.format(e))

        # 提取商品价格
        try:
            selectors = [
                "//span[@class='price']",
                "//div[@class='p-price']/span[2]",
                "//div[contains(@class, 'price-box')]//span[@class='price']",
                "//strong[@class='J-p-10145225792900']",
                "//span[@class='p-price']//span",
                "//strong[@id='J_p-10145225792900']"
            ]
            
            for selector in selectors:
                element = self._find_element_safe(By.XPATH, selector)
                if element:
                    price = element.text
                    print(f"找到价格元素，选择器：{selector}，内容：{price}")
                    if price:
                        price_xpath = re.findall(r'-?\d+\.?\d*e?-?\d*?', price)
                        if price_xpath:
                            item_info_dict['price'] = price_xpath[0]
                            break
                            
            if not item_info_dict['price']:
                print("未能找到价格信息，可能需要登录或页面结构已变化")
                
        except Exception as e:
            logging.warning('Crawl price failure: {}'.format(e))

        # 提取商品PLUS价格
        try:
            selectors = [
                "//div[@class='p-price-plus']//span[@class='price']",
                "//span[contains(@class, 'plus-price')]"
            ]
            for selector in selectors:
                element = self._find_element_safe(By.XPATH, selector)
                if element and element.text:
                    plus_price = element.text
                    plus_price_xpath = re.findall(r'-?\d+\.?\d*e?-?\d*?', plus_price)
                    if plus_price_xpath:
                        item_info_dict['plus_price'] = plus_price_xpath[0]
                        break
        except Exception as e:
            logging.warning('Crawl plus_price failure: {}'.format(e))

        # 提取商品副标题
        try:
            selectors = [
                "//div[@id='p-ad']",
                "//div[@class='sku-desc']",
                "//div[contains(@class, 'sku-subtitle')]"
            ]
            for selector in selectors:
                element = self._find_element_safe(By.XPATH, selector)
                if element and element.text:
                    item_info_dict['subtitle'] = element.text
                    break
        except Exception as e:
            logging.warning('Crawl subtitle failure: {}'.format(e))

    def get_huihui_item(self, item_id):
        huihui_info_dict = {"max_price": None, "min_price": None}
        url = 'https://zhushou.huihui.cn/productSense?phu=https://item.jd.com/' + item_id + '.html'
        try:
            self.chrome.get(url)
            url_text = self.chrome.find_element_by_tag_name('body').text
            info = json.loads(url_text)
            huihui_info_dict = {"max_price": info['max'], "min_price": info['min']}
            logging.info(huihui_info_dict)
        except decoder.JSONDecodeError as e:
            logging.warning('Crawl failure: {}'.format(e))
        except NoSuchElementException as e:
            logging.warning('Crawl failure: {}'.format(e))
        except TimeoutException as e:
            logging.warning('Crawl failure: {}'.format(e))
        return huihui_info_dict


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    start = time.time()
    c = Crawler()
    # c = Crawler({'http': '125.105.32.168:7305', 'https': '171.211.32.79:2456'})
    logging.debug(c.get_jd_item('5544068'))
    # logging.debug(c.get_huihui_item('2777811'))
    end = time.time()
    print(end - start)
