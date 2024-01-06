# chrome driver auto login
- 获取本机用户的所有 cookie，配合 selenium 直接登录。
- 获取本机用户的所有网站账号密码。



## export function
```python
__all__ = [
    "get_all_accounts",
    "get_all_cookies",
    "get_webdriver",
    "add_cookies",
    "auto_login"
]
```

```python
# 简单封装，返回webdriver
def get_webdriver(chrome_driver_path, headless=False):
    return driver

# 返回当前用户下所有的网站账号密码信息，可用filter_func过滤
# 调用此函数前请关闭Chrome，否则有可能因为文件被占用导致失败
def get_all_accounts(filter_func=None):
    return accounts

# 返回当前用户下所有的cookie，可用filter_func过滤
# 调用此函数前请关闭Chrome，否则有可能因为文件被占用导致失败
def get_all_cookies(filter_func=None):
    return cookies

# 使用get_all_cookies()返回的cookies为driver添加url的cookie
def add_cookies(driver, url, cookies):
    return 

# 自动登录
def auto_login(chrome_driver_path, url):
    driver = get_webdriver(chrome_driver_path)
    cookies = get_all_cookies()
    add_cookies(driver, url, cookies)
    driver.get(url)
    return driver
```



## usage

```python
def _test_auto_login():
    chrome_driver_path = r'd:\tmp\chromedriver.exe'
    url = 'https://bilibili.com'
    driver = auto_login(chrome_driver_path, url)
    # do something...
    driver.close()

def _test_get_all_accounts():
    accounts = get_all_accounts()
    for account in accounts:
        print(account)

def _test_get_all_cookies():
    cookies = get_all_cookies()
    for cookie in cookies:
        print(cookie)

if __name__ == '__main__':
    _test_get_all_accounts()
    _test_get_all_cookies()
    _test_auto_login()
```

