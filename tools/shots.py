"""docs/ をPC・スマホ幅で撮影し、横スクロールとJSエラーを調べる。
使い方: python3 tools/shots.py [ページ名...]   （例: index finance）  環境変数 DARK=1 でダーク表示"""
import asyncio, os, sys, threading, http.server, functools
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '_shots'; OUT.mkdir(exist_ok=True)
PAGES = sys.argv[1:] or ['index', 'finance', 'trading', 'hr']
DARK = os.environ.get('DARK') == '1'

def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / 'docs'))
    h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 5191), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()

async def main():
    serve()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, vp in [('pc', {'width': 1366, 'height': 900}), ('sp', {'width': 390, 'height': 844})]:
            ctx = await b.new_context(viewport=vp, color_scheme='dark' if DARK else 'light')
            pg = await ctx.new_page()
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            for page in PAGES:
                await pg.goto(f'http://127.0.0.1:5191/{page}.html', wait_until='domcontentloaded', timeout=60000)
                await pg.wait_for_timeout(1500)
                over = await pg.evaluate('document.documentElement.scrollWidth - window.innerWidth')
                await pg.screenshot(path=str(OUT / f'{page}-{name}{"-dark" if DARK else ""}.png'), full_page=True)
                print(f'{page} {name}: 横はみ出し {over}px', '／エラー: ' + '; '.join(errs) if errs else '')
                errs.clear()
            await ctx.close()
        await b.close()

asyncio.run(main())
