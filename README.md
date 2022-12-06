# chrome driver auto login
直接获取本机用户的cookie文件登录。

### 暴露函数
```python
__all__ = ["get_webdriver", "get_all_cookies", "add_cookies", "get_with_cookies"]
```

### usage
```python
if __name__ == '__main__':
    chrome_driver_path = r'd:\tmp\chromedriver.exe'
    url = 'https://bilibili.com'
    driver = get_with_cookies(chrome_driver_path, url)
    # do something...
    driver.close()
```
