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

    def __init__(self, proxy=None, skip_cookies=False, cookies_file=None):
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
        
        # 从配置文件中获取chromedriver路径
        chromedriver_path = '/usr/local/bin/chromedriver'  # 默认路径
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'monitor_items.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'chromedriver_path' in config:
                        chromedriver_path = config['chromedriver_path']
                        print(f"从配置文件加载ChromeDriver路径: {chromedriver_path}")
        except Exception as e:
            logging.warning(f"读取配置文件中的ChromeDriver路径失败: {e}")
            print(f"读取配置文件中的ChromeDriver路径失败: {e}")
        
        service = Service(chromedriver_path)
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
        
        # 设置cookies文件
        self.cookies_file = cookies_file or 'jd_pc_cookies.pkl'
        
        # 如果没有跳过加载cookies，则尝试加载
        if not skip_cookies:
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

    def save_cookies(self, cookies_file=None):
        """保存 cookies 到文件"""
        try:
            cookies = self.chrome.get_cookies()
            target_file = cookies_file or self.cookies_file
            if cookies:
                with open(target_file, 'wb') as f:
                    pickle.dump(cookies, f)
                return True
        except Exception as e:
            print(f"保存 cookies 失败: {e}")
        return False

    def load_cookies(self, cookies_file=None):
        """从文件加载 cookies"""
        try:
            target_file = cookies_file or self.cookies_file
            if os.path.exists(target_file):
                with open(target_file, 'rb') as f:
                    cookies = pickle.load(f)
                    if cookies:
                        # 先访问一下京东主页，这样才能添加 cookies
                        self.chrome.get('https://www.jd.com')
                        time.sleep(1)
                        
                        # 添加所有 cookies
                        for cookie in cookies:
                            try:
                                # 确保 cookie 有效
                                if 'expiry' in cookie and cookie['expiry'] < time.time():
                                    continue
                                self.chrome.add_cookie(cookie)
                            except Exception as e:
                                print(f"添加单个cookie时出错: {e}")
                                continue
                        
                        # 刷新页面以应用 cookies
                        self.chrome.refresh()
                        time.sleep(1)
                        
                        # 验证登录状态
                        if self.check_login_status():
                            print(f"Cookies 从 {target_file} 加载成功，已成功登录")
                            return True
                        else:
                            print(f"Cookies 从 {target_file} 加载失败，已失效")
                            # 删除失效的 cookies 文件
                            os.remove(target_file)
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
            
    def get_jd_item(self, item):
        """
        item: 可以是商品ID（如 '100038005189'）或完整URL（如 'https://item.jd.com/100038005189.html'）
        """
        import re
        item_info_dict = {"name": None, "price": None, "plus_price": None, "subtitle": None, "has_coupon": None, "coupon_detail_list": None}
        original_url = None
        # 彻底防止重复拼接
        if isinstance(item, str) and item.strip().startswith("http"):
            url = item.strip()
            m = re.search(r'/item.jd.com/(\\d+).html', url)
            item_id_for_debug = m.group(1) if m else "unknown"
        else:
            # 只允许数字作为商品ID，否则报错
            if not (isinstance(item, str) and item.isdigit()):
                raise ValueError(f"get_jd_item 参数异常，既不是url也不是纯数字ID: {item}")
            item_id_for_debug = item
            url = 'https://item.jd.com/' + str(item) + '.html'
        try:
            original_url = url
            self.chrome.get(url)
            time.sleep(2)
            # 只保留页面标题的输出，移除URL显示
            print(f"页面标题: {self.chrome.title}")
            
            # 已去除保存页面源码到 debug.html 的调试代码
            if "passport.jd.com" in self.chrome.current_url or "请登录" in self.chrome.page_source:
                print("检测到跳转到登录页，未登录或cookies失效")
                raise Exception("未登录或cookies失效")
            if "www.jd.com" in self.chrome.current_url:
                print("检测到跳转到京东首页，可能未通过反爬")
                raise Exception("被重定向到首页，反爬机制触发")
            
            # 在获取价格之前尝试点击"更多"按钮
            print("\n尝试点击'更多'按钮展开优惠信息...")
            self._click_more_button()
            print("点击操作完成，继续获取价格")
            
            main_price_xpaths = [
                "//span[@class='price J-p-']",  # 典型主售价
                "//span[@id='jd-price']",
                "//div[contains(@class,'p-price')]//span[contains(@class,'price')]",
                "//span[@class='p-price']/span",
                "//span[contains(@class,'price') and not(contains(@class,'plus'))]"
            ]
            main_price = None
            for xpath in main_price_xpaths:
                price_eles = self.chrome.find_elements(By.XPATH, xpath)
                if price_eles:
                    for ele in price_eles:
                        text = ele.text.strip().replace("￥", "").replace(",", "")
                        if text and text.replace('.', '', 1).isdigit():
                            main_price = text
                            print(f"主售价节点 (xpath: {xpath})，内容: {ele.text}")
                            break
                if main_price:
                    break
            if not main_price:
                price_spans = self.chrome.find_elements(By.XPATH, "//span[contains(@class,'price') or contains(@class,'p-price') or contains(@class,'jd-price') or contains(@class,'price J-p-') or @id='jd-price']")
                print(f"共找到 {len(price_spans)} 个价格相关元素:")
                for idx, ele in enumerate(price_spans):
                    print(f"[{idx}] class: {ele.get_attribute('class')}, id: {ele.get_attribute('id')}, 文本: {ele.text}")
                price_candidates = []
                for ele in price_spans:
                    text = ele.text.strip().replace("￥", "").replace(",", "")
                    if text and text.replace('.', '', 1).isdigit():
                        price_candidates.append(float(text))
                if price_candidates:
                    main_price = str(max(price_candidates))
                    print(f"降级选择最大价格作为主售价: {main_price}")
            item_info_dict = {'name': '', 'price': main_price, 'plus_price': None, 'subtitle': None}
            try:
                WebDriverWait(self.chrome, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "sku-name"))
                )
                self.chrome.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                self._extract_item_info(item_info_dict)
                
                # 价格找到后，再次检查是否有优惠券（以防点击"更多"按钮后有变化）
                print("\n--- 检查优惠券状态（价格获取后） ---")
                item_info_dict['has_coupon'], coupon_detail_list = self.check_has_coupon()
                item_info_dict['coupon_detail_list'] = coupon_detail_list
                if item_info_dict['has_coupon']:
                    print(f"优惠券详细信息：{coupon_detail_list}")
                
            except TimeoutException:
                print("等待商品信息加载超时")
        except Exception as e:
            logging.warning('Crawl failure: {}'.format(e))
            print(f"发生错误: {str(e)}")
        finally:
            if any(value is not None for value in item_info_dict.values()):
                self.save_cookies()
            logging.info('Crawl finished')
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
            
    def _click_more_button(self):
        """尝试点击页面上的'更多'按钮，弹出右侧界面"""
        try:
            # 使用精确的CSS选择器查找more-btn元素
            more_btn = self.chrome.find_element(By.CSS_SELECTOR, "span.more-btn")
            
            # 如果找到了元素并且可见，使用JavaScript点击它
            if more_btn.is_displayed():
                self.chrome.execute_script("arguments[0].click();", more_btn)
                time.sleep(1)  # 等待弹出层显示
        except Exception as e:
            logging.debug(f"点击'更多'按钮失败: {e}")
            
    def check_has_coupon(self):
        """仅根据新版京东优惠券区域判断并提取所有优惠券信息"""
        try:
            coupon_detail_list = []
            coupons_box = self.chrome.find_elements(By.CSS_SELECTOR, "div.coupons-list-box")
            if coupons_box:
                coupon_quans = coupons_box[0].find_elements(By.CSS_SELECTOR, ".coupon-quan")
                for cq in coupon_quans:
                    try:
                        price = cq.find_element(By.CSS_SELECTOR, ".coupon-quan-left-price").text.strip()
                    except Exception:
                        price = ""
                    try:
                        condition = cq.find_element(By.CSS_SELECTOR, ".coupon-quan-right-price").text.strip()
                    except Exception:
                        condition = ""
                    try:
                        expire = cq.find_element(By.CSS_SELECTOR, ".coupon-quan-right-font").text.strip()
                    except Exception:
                        expire = ""
                    coupon_detail_list.append({
                        "面值": price,
                        "门槛": condition,
                        "有效期": expire
                    })
                print("【检测到优惠券】此商品有优惠券可用！！！")
                return True, coupon_detail_list
            else:
                print("【未检测到优惠券】此商品暂无优惠券")
                return False, []
        except Exception as e:
            print(f"检查优惠券时出错: {e}")
            return False, []

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
    # logging.debug(c.get_jd_item('5544068'))
    # logging.debug(c.get_huihui_item('2777811'))
    end = time.time()
    print(end - start)
