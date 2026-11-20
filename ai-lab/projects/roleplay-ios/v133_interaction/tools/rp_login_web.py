"""HTTPS login portal for a private RP authority. Game traffic uses its own mTLS port."""
import asyncio
from html import escape
import ssl

from aiohttp import web

COOKIE = '__Host-rplogin'
HEADERS = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
           'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
           'X-Content-Type-Options': 'nosniff'}
FORM = '''<form action="/login" method="post">
<label>Tài khoản<input name="username" autocomplete="username" autocapitalize="none" maxlength="32" required></label>
<label>Mật khẩu<input name="password" type="password" autocomplete="current-password" maxlength="128" required></label>
<button>Đăng nhập</button></form>'''


def page(content, status=200):
    return web.Response(content_type='text/html', headers=HEADERS, status=status, text='''<!doctype html>
<html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Police RP · Đăng nhập</title><style>
*{box-sizing:border-box}body{margin:0;background:#10212c;color:#f4f7ef;font:17px/1.5 Inter,system-ui,sans-serif}
main{max-width:27rem;margin:clamp(2rem,12vh,8rem) auto;padding:1.5rem}h1{margin:.25em 0}
label,input,button{display:block;width:100%}label{margin:1rem 0}input,button{padding:.75rem;border-radius:.35rem;font:inherit}
input{border:1px solid #a7bdc7}button{background:#a6e3bd;color:#10212c;border:0;font-weight:700;cursor:pointer}
</style><main><h1>Police Roleplay</h1>''' + content + '</main></html>')


def application(accounts, origin, revoke_peers):
    async def home(request):
        grant = accounts.validate(accounts.token_key(request.cookies.get(COOKIE)), touch=True)
        if not grant:
            return page(FORM)
        return page(f'<p>Đã đăng nhập <strong>{escape(grant.name)}</strong>.</p>'
                    '<p>Mở GTA với hồ sơ RP tương ứng rồi chọn <b>RP riêng → Tham gia RP</b>.</p>'
                    '<form action="/logout" method="post"><button>Đăng xuất</button></form>')

    async def submit(request):
        if request.headers.get('Origin') != origin:
            return page('<p>Hãy mở lại trang đăng nhập của máy chủ.</p>', 403)
        if request.path == '/logout':
            accounts.logout(request.cookies.get(COOKIE))
            revoke_peers()
            response = web.HTTPSeeOther('/', headers=HEADERS)
            response.set_cookie(COOKIE, '', path='/', secure=True, httponly=True, samesite='Strict', max_age=0)
            raise response
        if request.content_type != 'application/x-www-form-urlencoded':
            return page('<p>Biểu mẫu không hợp lệ.</p>', 415)
        try:
            async with asyncio.timeout(5):
                fields = await request.post()
        except (ValueError, TimeoutError):
            return page('<p>Biểu mẫu không hợp lệ.</p>', 400)
        if len(fields) != 2 or set(fields) != {'username', 'password'}:
            return page('<p>Biểu mẫu không hợp lệ.</p>', 400)
        token = await accounts.login(fields['username'], fields['password'], request.remote)
        if not token:
            return page('<p role="alert">Đăng nhập chưa thành công. Kiểm tra tài khoản hoặc thử lại sau.</p>' + FORM, 401)
        # Switching accounts in one browser must also retire its former RP grant.
        accounts.logout(request.cookies.get(COOKIE))
        revoke_peers()
        response = web.HTTPSeeOther('/', headers=HEADERS)
        response.set_cookie(COOKIE, token, path='/', secure=True, httponly=True, samesite='Strict')
        raise response

    app = web.Application(client_max_size=4096)
    app.router.add_get('/', home)
    app.router.add_post('/login', submit)
    app.router.add_post('/logout', submit)
    return app


async def start_portal(accounts, host, port, origin, credentials, revoke_peers):
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(credentials.certificate, credentials.private_key)
    runner = web.AppRunner(application(accounts, origin, revoke_peers), access_log=None,
                           auto_decompress=False, max_field_size=4096, shutdown_timeout=3)
    await runner.setup()
    try:
        await web.TCPSite(runner, host, port, ssl_context=tls).start()
    except BaseException:
        await runner.cleanup()
        raise
    return runner
