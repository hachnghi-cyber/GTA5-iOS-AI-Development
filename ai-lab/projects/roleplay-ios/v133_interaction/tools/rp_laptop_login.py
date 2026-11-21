"""Sign in from the laptop using the login portal and the kit's private CA."""
import argparse
import getpass
from http.cookiejar import CookieJar
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    origin = config['login']['origin']
    if urllib.parse.urlsplit(origin).scheme != 'https':
        parser.error('HTTPS is required')
    tls = ssl.create_default_context(cafile=str(args.config.resolve().parent / config['trusted_ca']))
    jar = CookieJar()
    browser = urllib.request.build_opener(urllib.request.ProxyHandler({}),
              urllib.request.HTTPSHandler(context=tls), urllib.request.HTTPCookieProcessor(jar))
    def post(path, data):
        request = urllib.request.Request(origin + path, data=urllib.parse.urlencode(data).encode(),
                                         headers={'Origin': origin})
        with browser.open(request, timeout=8) as response:
            response.read()
    try:
        post('/login', {'username': input('Tài khoản RP: ').strip(),
                        'password': getpass.getpass('Mật khẩu: ')})
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
        parser.exit(1, 'Đăng nhập chưa thành công. Kiểm tra tài khoản hoặc thử lại sau.\n')
    if not any(cookie.name == '__Host-rplogin' for cookie in jar):
        parser.exit(1, 'Máy chủ chưa xác nhận đăng nhập.\n')
    try:
        input('Đã đăng nhập. Mở GTA → RP riêng → Tham gia RP. Nhấn Enter để đăng xuất. ')
    finally:
        post('/logout', {})


if __name__ == '__main__':
    main()
