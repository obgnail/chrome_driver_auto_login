import base64
import ctypes.wintypes
import json
import os
import platform
import shutil
import sqlite3
import time
from contextlib import contextmanager
from urllib.parse import urlparse

import win32crypt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

__all__ = [
    "get_all_accounts",
    "get_all_cookies",
    "get_webdriver",
    "add_cookies",
    "auto_login"
]

if platform.system().lower() != 'windows':
    raise "unsupported platform"


def _get_user_file_path():
    local_lapp_data = os.environ['LOCALAPPDATA']
    user_data_dir = os.path.join(local_lapp_data, 'Google', 'Chrome', 'User Data')
    local_state_file_path = os.path.join(user_data_dir, 'Local State')
    cookies_file_path = os.path.join(user_data_dir, 'Default', 'Network', 'Cookies')
    login_data_path = os.path.join(user_data_dir, 'Default', 'Login Data')
    return local_state_file_path, cookies_file_path, login_data_path


def _query_sqlite(file, sql, item_func, filter_func=None):
    conn = sqlite3.connect(file)
    try:
        rows = conn.execute(sql).fetchall()
    finally:
        conn.close()

    result = []

    for row in rows:
        data = item_func(row)
        if filter_func is not None and filter_func(data) == True:
            continue
        result.append(data)

    return result


def _get_encrypted_cookies_from_file(file_path, filter_func=None):
    return _query_sqlite(
        file=file_path,
        sql='SELECT host_key, name, encrypted_value, path, is_secure, expires_utc FROM cookies;',
        item_func=lambda row: dict(domain=row[0], name=row[1], value=row[2], path=row[3],
                                   secure=False if row[4] == 0 else True,
                                   expiry=max(int(row[5] / 1000000 - 11644473600), 0)),
        filter_func=filter_func
    )


def _get_encrypted_accounts_from_file(file_path, filter_func=None):
    return _query_sqlite(
        file=file_path,
        sql='SELECT signon_realm, username_value, password_value FROM logins;',
        item_func=lambda row: dict(domain=row[0], user=row[1], password=row[2]),
        filter_func=filter_func
    )


def _get_accounts_decrypt_key(local_state):
    encrypted_key = _get_key_string(local_state)
    key = _dpapi_decrypt(encrypted_key)
    return key


def _get_cookies_decrypt_key(local_state):
    encrypted_key = _get_key_string(local_state)
    key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    return key


# 读取chrome保存在json文件中的key
def _get_key_string(local_state):
    with open(local_state, 'r', encoding='utf-8') as f:
        encrypted_key = json.load(f)['os_crypt']['encrypted_key']
    encrypted_key_with_header = base64.b64decode(encrypted_key.encode())  # base64解码
    key = encrypted_key_with_header[5:]
    return key


def _dpapi_decrypt(encrypted):
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', ctypes.wintypes.DWORD),
                    ('pbData', ctypes.POINTER(ctypes.c_char))]

    p = ctypes.create_string_buffer(encrypted, len(encrypted))
    blobin = DATA_BLOB(ctypes.sizeof(p), p)
    blobout = DATA_BLOB()
    retval = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout))
    if not retval:
        raise ctypes.WinError()
    result = ctypes.string_at(blobout.pbData, blobout.cbData)
    ctypes.windll.kernel32.LocalFree(blobout.pbData)
    return result


def _aesgcm_decrypt(key, encrypted):
    nonce, cipher_bytes = encrypted[3:15], encrypted[15:]
    plain_bytes = AESGCM(key).decrypt(nonce, cipher_bytes, None)
    plain_text = plain_bytes.decode('utf-8')
    return plain_text


def _aes_decrypt(key, encrypted):
    nonce, cipher_bytes = encrypted[3:15], encrypted[15:]
    cipher = Cipher(algorithms.AES(key), mode=modes.GCM(nonce), backend=default_backend())
    plain_text = cipher.decryptor().update(cipher_bytes)
    return plain_text


def _decrypt_cookies(crypt_cookies, key):
    for cookie in crypt_cookies:
        cookie['value'] = _aesgcm_decrypt(key, cookie['value'])
    return crypt_cookies


def _decrypt_accounts(crypt_accounts, key):
    def _decrypt_cookie(password):
        if password[:4] == b'\x01\x00\x00\x00':  # v80之前
            return _dpapi_decrypt(password).decode()
        elif password[:3] == b'v10':  # v80及之后
            return _aes_decrypt(key, password)[:-16].decode()

    for account in crypt_accounts:
        account['password'] = _decrypt_cookie(account['password'])
    return crypt_accounts


@contextmanager
def _copy_file(src):
    dst = '%s.temp' % time.time()
    try:
        shutil.copyfile(src, dst)
        yield dst
    finally:
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
        if cookie['expiry'] == 0:
            del cookie['expiry']
        driver.add_cookie(cookie)


def get_all_cookies(filter_func=None):
    local_state_file, cookies_file, _ = _get_user_file_path()
    with _copy_file(local_state_file) as f1, _copy_file(cookies_file) as f2:
        key = _get_cookies_decrypt_key(f1)
        encrypted_cookies = _get_encrypted_cookies_from_file(f2, filter_func)
    cookies = _decrypt_cookies(encrypted_cookies, key)
    return cookies


def get_all_accounts(filter_func=None):
    local_state_file, _, login_data_file = _get_user_file_path()
    with _copy_file(local_state_file) as f1, _copy_file(login_data_file) as f2:
        key = _get_accounts_decrypt_key(f1)
        encrypted_accounts = _get_encrypted_accounts_from_file(f2, filter_func)
    accounts = _decrypt_accounts(encrypted_accounts, key)
    return accounts


def auto_login(chrome_driver_path, url):
    driver = get_webdriver(chrome_driver_path)
    cookies = get_all_cookies()
    add_cookies(driver, url, cookies)
    driver.get(url)
    return driver


def _test_auto_login():
    chrome_driver_path = r'd:\tmp\chromedriver.exe'
    url = 'https://bilibili.com'
    driver = auto_login(chrome_driver_path, url)
    time.sleep(10)
    driver.close()


def _test_get_all_accounts():
    accounts = get_all_accounts()
    for account in accounts:
        print(account)


if __name__ == '__main__':
    _test_get_all_accounts()
    # _test_auto_login()
