import base64
import json
import os
import shutil
import sqlite3
import time
from contextlib import contextmanager
from urllib.parse import urlparse

import win32crypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

__all__ = ["get_webdriver", "get_all_cookies", "add_cookies", "get_with_cookies"]


def _get_user_file_path():
    local_lapp_data = os.environ['LOCALAPPDATA']
    user_data_dir = os.path.join(local_lapp_data, 'Google', 'Chrome', 'User Data')
    local_state_file_path = os.path.join(user_data_dir, 'Local State')
    cookies_file_path = os.path.join(user_data_dir, 'Default', 'Network', 'Cookies')
    return cookies_file_path, local_state_file_path


def _get_encrypted_cookies_from_file(cookies_file_path, filter_func=None):
    sql = 'SELECT host_key, name, encrypted_value, path, is_secure, expires_utc FROM cookies;'
    conn = sqlite3.connect(cookies_file_path)
    try:
        result = conn.execute(sql).fetchall()
    finally:
        conn.close()

    cookies = []
    for row in result:
        cookie = dict(
            domain=row[0],
            name=row[1],
            value=row[2],
            path=row[3],
            secure=False if row[4] == 0 else True,
            expiry=int(row[5] / 1000000 - 11644473600)
        )

        if filter_func is not None and filter_func(cookie) == True:
            continue
        cookies.append(cookie)

    return cookies


def _get_decrypt_key(local_state_file_path):
    base64_key = _get_key_string(local_state_file_path)
    key = _pull_the_key(base64_key)
    return key


# 读取chrome保存在json文件中的key
def _get_key_string(local_state):
    with open(local_state, 'r', encoding='utf-8') as f:
        s = json.load(f)['os_crypt']['encrypted_key']
    return s


# base64解码，DPAPI解密，得到真实的AESGCM key(bytes)
def _pull_the_key(base64_encrypted_key):
    encrypted_key_with_header = base64.b64decode(base64_encrypted_key)
    encrypted_key = encrypted_key_with_header[5:]
    key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    return key


# AESGCM解密
def _decrypt_data(key, data):
    nonce, cipher_bytes = data[3:15], data[15:]
    aesgcm = AESGCM(key)
    plain_bytes = aesgcm.decrypt(nonce, cipher_bytes, None)
    plain_text = plain_bytes.decode('utf-8')
    return plain_text


def _decrypt_cookies(crypt_cookies, key):
    for crypt_cookie in crypt_cookies:
        crypt_cookie['value'] = _decrypt_data(key, crypt_cookie['value'])
    return crypt_cookies


@contextmanager
def _copy_file(src):
    dst = '%s.temp' % time.time()
    shutil.copyfile(src, dst)
    yield dst
    if os.path.exists(dst):
        os.remove(dst)


def get_webdriver(chrome_driver_path, headless=False):
    options = Options()
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_argument('--disable-blink-features=AutomationControlled')
    if headless:
        options.add_argument("--headless")
    driver = webdriver.Chrome(executable_path=(chrome_driver_path), options=options)
    return driver


def add_cookies(driver, url, cookies):
    hostname = urlparse(url).hostname
    if not hostname:
        raise "illegal url"
    if not hostname.startswith('.'):
        hostname = '.' + hostname

    driver.delete_all_cookies()
    driver.get(url)  # selenium添加cookie前需要先get一下
    for cookie in cookies:
        if cookie['domain'] != hostname:
            continue
        driver.add_cookie(cookie)


# filter_func: 用于过滤不需要的cookie,可为None
def get_all_cookies(filter_func=None):
    cookies_file, local_state_file = _get_user_file_path()
    with _copy_file(cookies_file) as f1, _copy_file(local_state_file) as f2:
        encrypted_cookies = _get_encrypted_cookies_from_file(f1, filter_func)
        key = _get_decrypt_key(f2)
    cookies = _decrypt_cookies(encrypted_cookies, key)
    return cookies


def get_with_cookies(chrome_driver_path, url):
    cookies = get_all_cookies()
    driver = get_webdriver(chrome_driver_path)
    add_cookies(driver, url, cookies)
    driver.get(url)
    return driver


if __name__ == '__main__':
    chrome_driver_path = r'd:\tmp\chromedriver.exe'
    url = 'https://bilibili.com'
    driver = get_with_cookies(chrome_driver_path, url)
    time.sleep(10)
    driver.close()
