"""業界研究ガイドのサイトを作る。content/ の中身から docs/ に HTML を書き出す。
使い方: python3 build.py
"""
import html, json, re, shutil
from pathlib import Path

from content.fin import PAGE as FINANCE
from content.grp_a import TRADING, CONSULTING, IT, AUTO
from content.grp_b import ELECTRONICS, MATERIALS, FOOD, REALESTATE
from content.grp_c import INFRA, MEDIA, TRAVEL, HR
from content import index as IX
from content.common import YUHO_COLS, GOAL_COLS
from content.chara import CHARA
from content import partners as PT
from content import tsumari as TS
from content.glossary import G as GLOSS, CATS as GCATS
for _k, _c in CHARA.items():
    _c['id'] = _k

ROOT = Path(__file__).parent
OUT = ROOT / 'docs'
PAGES = [FINANCE, TRADING, CONSULTING, IT, AUTO, ELECTRONICS, MATERIALS, FOOD, REALESTATE, INFRA, MEDIA, TRAVEL, HR]
SITE = '業界研究ガイド'
ASOF = '2026年10月21日時点'
BASE = 'https://riri-1818.github.io/gyokai-guide/'

# 広告とSearch Console。審査に申し込んだら、もらったIDをここに入れて build し直す。
ADSENSE_CLIENT = 'ca-pub-6874249952104585'   # 例: 'ca-pub-1234567890123456'（空なら広告のコードは出さない）
SEARCH_CONSOLE = 'QB6o8pXq2sH4qfSRkQOqgZA5gKZXzM9xfiC0SvluM5U'   # Search Console の「HTMLタグ」の content の値
WEB3FORMS_KEY = '69066896-0033-4d7f-86ce-89e1c2710472'  # ワーホリ実務ノートと同じ。送信は本人のメールに届く


# ---------- 文字の整形 ----------
def md(text):
    """[文字](URL) と **太字** だけを HTML にする。"""
    s = html.escape(text, quote=False)

    def link(m):
        label, url = m.group(1), m.group(2)
        ext = url.startswith('http')
        attrs = ' target="_blank" rel="noopener"' if ext else ''
        return f'<a href="{html.escape(url)}"{attrs}>{label}</a>'
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    return s


def short(p):
    return p.get('short', p['name'])


# ---------- 用語の点線リンク ----------
GBYK = {g['k']: g for g in GLOSS}
_ALIAS = sorted(((html.escape(a, quote=False), g['k']) for g in GLOSS for a in g['al']), key=lambda x: -len(x[0]))
_AMAP = dict(_ALIAS)


def _pat(a):
    p = re.escape(a)
    if re.match(r'[A-Za-z]', a[0]):
        p = r'(?<![A-Za-z0-9])' + p
    if re.match(r'[A-Za-z0-9]', a[-1]):
        p += r'(?![A-Za-z0-9])'
    return p


GL_RE = re.compile('|'.join(_pat(a) for a, _ in _ALIAS))
# この中の文字には点線を引かない（リンク・見出し・ボタン・図の中など）
GL_SKIP = {'a', 'h1', 'h2', 'h3', 'h4', 'button', 'script', 'style', 'svg', 'nav', 'summary', 'figcaption',
           'thead', 'title', 'textarea', 'label', 'dt', 'figure'}


def gloss_link(h, used_all):
    """本文の用語に、章ごとに最初の1回だけ点線ボタンを付ける。used_all に使った用語の id を足す。"""
    out, stack, used, pos = [], [], set(), 0

    def sub(text):
        def one(m):
            k = _AMAP[m.group(0)]
            if k in used:
                return m.group(0)
            used.add(k)
            used_all.add(k)
            return f'<button type="button" class="gw" data-g="{k}" aria-haspopup="dialog">{m.group(0)}</button>'
        return GL_RE.sub(one, text)

    for m in re.finditer(r'<(/?)([a-zA-Z0-9]+)[^>]*?(/?)>', h):
        text = h[pos:m.start()]
        out.append(text if stack else sub(text))
        closing, name, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        if not closing and (name == 'section' or 'class="hero' in m.group(0)):
            used.clear()
        if name in GL_SKIP and not selfclose:
            if closing:
                if stack and stack[-1] == name:
                    stack.pop()
            else:
                stack.append(name)
        out.append(m.group(0))
        pos = m.end()
    out.append(h[pos:] if stack else sub(h[pos:]))
    return ''.join(out)


def gloss_data(keys):
    data = {k: GBYK[k] for k in sorted(keys)}
    return ('<script type="application/json" id="gl-data">'
            + json.dumps(data, ensure_ascii=False).replace('</', '<\\/') + '</script>')


def tsumari(text):
    return f'<p class="tsumari"><span>つまり？</span>{md(text)}</p>' if text else ''


# ---------- 部品 ----------
def table(cols, rows, cls=''):
    head = ''.join(f'<th scope="col">{md(c)}</th>' for c in cols)
    body = ''
    for r in rows:
        cells = f'<th scope="row" data-label="{html.escape(cols[0])}">{md(r[0])}</th>'
        for c, v in zip(cols[1:], r[1:]):
            neg = ' class="neg"' if re.fullmatch(r'-\d+(\.\d+)?%', v) else ''
            cells += f'<td data-label="{html.escape(c)}"{neg}>{md(v)}</td>'
        body += f'<tr>{cells}</tr>'
    return f'<div class="tbl {cls}"><table class="stack"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def timeline(rows):
    items = ''.join(
        f'<li><div class="tl-when">{md(w)}</div><div class="tl-body"><p class="tl-ev">{md(e)}</p>'
        f'<p class="tl-mean"><span>業界にとっての意味</span>{md(m)}</p></div></li>' for w, e, m in rows)
    return f'<ol class="timeline">{items}</ol>'


def news(items, pid=''):
    out = ''
    for i, (title, paras) in enumerate(items, 1):
        body = ''.join(f'<p>{md(p)}</p>' for p in paras) + tsumari(TS.NEWS.get((pid, title)))
        out += f'<article class="news-item"><span class="news-no">{i}</span><div><h3>{md(title)}</h3>{body}</div></article>'
    return f'<div class="news">{out}</div>'


def winds(rows):
    out = ''
    for theme, up, down, q in rows:
        out += (f'<article class="wind"><h3>{md(theme)}</h3>'
                f'<div class="w up"><span class="lbl">追い風</span><p>{md(up)}</p></div>'
                f'<div class="w down"><span class="lbl">逆風・課題</span><p>{md(down)}</p></div>'
                f'<div class="w q"><span class="lbl">面接で語れる問い</span><p>{md(q)}</p></div></article>')
    return f'<div class="winds">{out}</div>'


def goals(rows):
    out = ''.join(f'<article class="goal"><h4>{md(c)}</h4><div class="g"><span class="lbl">{md(GOAL_COLS[1])}</span><p>{md(g)}</p></div>'
                  f'<div class="g risk"><span class="lbl">{md(GOAL_COLS[2])}</span><p>{md(r)}</p></div></article>' for c, g, r in rows)
    return f'<div class="goals">{out}</div>'


def finds(items):
    lis = ''.join(f'<li><strong>{md(b)}</strong>{(" " + md(t)) if t else ""}</li>' for b, t in items)
    return f'<ul class="finds">{lis}</ul>'


def motive(items):
    out = ''.join(f'<div class="mv {k}"><span class="lbl">{md(l)}</span><p>{md(t)}</p></div>' for l, t, k in items)
    return f'<div class="motive">{out}</div>'


def steps(items):
    lis = ''.join(f'<li><h3>{md(t)}</h3><p>{md(d)}</p><p class="ex">{md(e)}</p></li>' for t, d, e in items)
    return f'<ol class="steps">{lis}</ol>'


def gainlose(rows):
    def kind(v):
        return 'up' if '得' in v else 'down'
    out = ''.join(f'<div class="gl {kind(v)}"><span class="tag {kind(v)}">{md(v)}</span><h4>{md(w)}</h4><p>{md(y)}</p></div>'
                  for w, v, y in rows)
    return f'<div class="gainlose">{out}</div>'


def sheet(rows):
    head = '<th scope="col">物差し</th>' + ''.join(f'<th scope="col">会社{x}</th>' for x in 'ABC')
    body = ''
    for i, r in enumerate(rows):
        cells = ''.join(f'<td data-label="会社{x}"><div class="cell" contenteditable="true" data-key="sheet-{i}-{x}" '
                        f'aria-label="{html.escape(r)}・会社{x}"></div></td>' for x in 'ABC')
        body += f'<tr><th scope="row" data-label="物差し">{md(r)}</th>{cells}</tr>'
    return (f'<p class="note">マスをタップすると書き込めます。書いた内容はこの端末のブラウザにだけ保存されます。</p>'
            f'<div class="tbl sheet"><table class="stack"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
            f'<button type="button" class="btn-ghost" id="sheet-clear">シートを空にする</button>')


def chart(spec):
    data = html.escape(json.dumps(spec, ensure_ascii=False), quote=True)
    tbl = ''
    if spec['type'] == 'line':
        rows = [[co] + [('—' if v is None else f'{v:,}') for v in vals] for co, vals in spec['series'].items()]
        tbl = table(['会社'] + spec['x'], rows, 'compact')
    elif spec['type'] == 'step':
        tbl = table(['決定日', '政策金利'], [[d, lab] for d, _, lab in spec['rows']], 'compact')
    elif spec['type'] == 'roe':
        rows = [[ind, '、'.join(f'{c} {v}%' for c, v in cos)] for ind, cos in spec['rows']]
        tbl = table(['業界', '各社のROE'], rows, 'compact')
    return (f'<figure class="chart"><div class="chart-head"><p class="chart-title">{md(spec["title"])}</p>'
            f'<p class="chart-sub">{md(spec["sub"])}</p></div>'
            f'<div class="chart-body" data-chart="{data}"></div>'
            f'<figcaption>{md(spec["caption"])}</figcaption>'
            f'<details><summary>数字を表で見る</summary>{tbl}</details></figure>')


def diagram(kind, caption):
    if kind == 'spread':
        body = '''
<p class="dg-title">銀行は「安く借りて、高く貸す」差で稼ぐ</p>
<p class="dg-sub">預金は「あなたが銀行にお金を貸している」状態。だから銀行はあなたに利息を払う</p>
<div class="sp-row">
  <div class="sp-box"><b>あなた（預金者）</b><small>年0.5%の利息をもらう</small></div>
  <div class="sp-flow"><span class="fwd">預金100万円</span><span class="back">利息 5,000円</span></div>
  <div class="sp-box main"><b>銀行</b><small>安く借りて高く貸す</small></div>
  <div class="sp-flow"><span class="fwd">貸出100万円</span><span class="back">利息 約12,000円</span></div>
  <div class="sp-box"><b>借りる人・企業</b><small>年1.2%前後の利息を払う</small></div>
</div>
<div class="sp-result">差の約7,000円が銀行の稼ぎ＝<span class="mark">利ざや</span></div>
<p class="dg-note">※100万円を1年間預ける・貸す場合の例。普通預金0.5%（2026年11月〜、メガバンク）、変動型住宅ローン約1.2%で計算。人件費や貸し倒れへの備えも、この差から払います。</p>'''
    else:
        routes = [('預金', '銀行', '貸す当事者・利ざやで稼ぐ', '融資'), ('株・債券', '証券会社', '市場への仲介・手数料で稼ぐ', '発行を仲介'),
                  ('保険料', '保険会社', 'リスクを引き受け運用で稼ぐ', '運用・投資'), ('投資信託', '資産運用会社', '投資先を選ぶ・残高×報酬', '運用・投資')]
        rs = ''.join(f'<div class="fl-route"><span class="fl-in">{a}</span><div class="fl-box"><b>{b}</b><small>{c}</small></div><span class="fl-out">{d}</span></div>'
                     for a, b, c, d in routes)
        body = f'''
<p class="dg-title">お金は「余っている人」から「必要な人」へ、4つのルートで流れる</p>
<p class="dg-sub">家計は利息・配当・保険金で見返りを受け取り、金融機関は途中の差額や手数料で稼ぐ</p>
<div class="fl-grid">
  <div class="fl-side"><b>家計（個人）</b><small>お金が余っている側</small><small>預金・NISA・保険</small></div>
  <div class="fl-routes">{rs}</div>
  <div class="fl-side"><b>企業・国</b><small>お金が必要な側</small><small>設備投資・M＆A・国債</small></div>
</div>
<div class="fl-boj"><span>金利</span>日本銀行が政策金利（いまは1.25%）＝お金の値段を決め、全ルートの稼ぎを左右する</div>'''
    return f'<figure class="diagram dg-{kind}">{body}<figcaption>{md(caption)}</figcaption></figure>'


def block(b, page):
    t = b[0]
    if t == 'p': return f'<p>{md(b[1])}</p>'
    if t == 'h3': return f'<h3 class="sub">{md(b[1])}</h3>'
    if t == 'note': return f'<p class="note">{md(b[1])}</p>'
    if t == 'callout': return f'<div class="callout"><strong>{md(b[1])}</strong><p>{md(b[2])}</p></div>'
    if t == 'formula': return f'<div class="formula"><strong>型</strong><p>{md(b[1])}</p></div>'
    if t == 'table': return table(b[1], b[2])
    if t == 'timeline': return timeline(b[1])
    if t == 'news': return news(b[1], page['id'])
    if t == 'winds': return winds(b[1])
    if t == 'goals': return goals(b[1])
    if t == 'finds': return finds(b[1])
    if t == 'motive': return motive(b[1])
    if t == 'steps': return steps(b[1])
    if t == 'gainlose': return gainlose(b[1])
    if t == 'sheet': return sheet(b[1])
    if t == 'yuho': return table(YUHO_COLS, b[1], 'yuho')
    if t == 'chart': return chart(page['charts'][b[1]])
    if t == 'diagram': return diagram(b[1], b[2])
    raise ValueError(t)


# ---------- キャラクター ----------
def seal(c, cls=''):
    """キャラのイラスト（assets/chara/<業界id>.svg）。"""
    return f'<span class="seal {cls}" aria-hidden="true"><img src="assets/chara/{c["id"]}.svg" alt="" width="200" height="200" loading="lazy"></span>'


def chara_card(pid):
    c = CHARA[pid]
    prof = ''.join(f'<div><dt>{md(k)}</dt><dd>{md(v)}</dd></div>' for k, v in c['profile'])
    daily = ''.join(f'<li><b>{md(t)}</b><p>{md(d)}</p></li>' for t, d in c['daily'])
    return (f'<section class="chara" style="--h:{c["hue"]}" aria-label="この業界のキャラクター">'
            f'<div class="ch-top">{seal(c)}<div class="ch-id"><p class="ch-role">{md(c["role"])}</p>'
            f'<p class="ch-name">{md(c["name"])}<small>{md(c["kana"])}</small></p></div></div>'
            f'<p class="ch-intro">{md(c["intro"])}</p>'
            f'<dl class="ch-prof">{prof}</dl>'
            f'<h2 class="ch-daily-h">キミの毎日にいる{md(c["name"])}</h2><ol class="ch-daily">{daily}</ol></section>')


def say(pid, sid):
    c = CHARA[pid]
    line = c['says'].get(sid)
    if not line:
        return ''
    return f'<div class="say" style="--h:{c["hue"]}">{seal(c, "sm")}<p><b>{md(c["name"])}</b>{md(line)}</p></div>'


# ---------- 無料の相談先 ----------
def soudan():
    cards = ''
    for x in PT.SOUDAN:
        pr = '<span class="pr">PR</span>' if x['pr'] else ''
        link = (f'<a class="sd-link" href="{html.escape(x["url"])}" target="_blank" rel="noopener{" sponsored" if x["pr"] else ""}">{md(x["label"])}</a>'
                if x['url'] else '')
        note = f'<p class="sd-note">{md(x["note"])}</p>' if x['note'] else ''
        cards += (f'<article class="sd-card"><h3>{md(x["name"])}{pr}</h3><p class="sd-by">{md(x["by"])}</p>'
                  f'<p>{md(x["what"])}</p>{note}{link}</article>')
    return (f'<div class="sd-grid">{cards}</div>'
            f'<div class="callout"><strong>エージェントはなぜ無料？</strong><p>{md(PT.WHY_FREE)}</p></div>'
            f'<p class="note">学生が無料で使えて、人に相談できるところだけを載せています。各公式ページの記載は{PT.CHECKED}に確認しました。'
            f'料金や対象は変わることがあるので、申し込む前に公式ページで確かめてください。</p>')


def soudan_sec(no):
    return (f'<section id="soudan" class="sec"><div class="sec-h"><span class="sec-no">{no}</span>'
            f'<h2>ひとりで抱えないで：無料で相談できる場所</h2></div>{soudan()}</section>')


# ---------- 枠 ----------
def sidebar(current, sections):
    items = f'<li><a href="index.html"{" aria-current=page" if current == "index" else ""}>総まとめ</a>'
    if current == 'index':
        items += '<ul>' + ''.join(f'<li><a href="#{i}">{n}</a></li>' for i, n in sections) + '</ul>'
    items += '</li>'
    items += f'<li><a href="yougo.html"{" aria-current=page" if current == "yougo" else ""}>やさしい用語集</a></li>'
    for p in PAGES:
        cur = p['id'] == current
        items += f'<li><a href="{p["id"]}.html"{" aria-current=page" if cur else ""}>{short(p)}</a>'
        if cur:
            items += '<ul>' + ''.join(f'<li><a href="#{i}">{n}</a></li>' for i, n in sections) + '</ul>'
        items += '</li>'
    items += (f'<li class="side-meta"><a href="about.html"{" aria-current=page" if current == "about" else ""}>運営者・お問い合わせ</a></li>'
              f'<li class="side-meta"><a href="privacy.html"{" aria-current=page" if current == "privacy" else ""}>プライバシーポリシー</a></li>')
    return f'<nav class="side" id="side" aria-label="ページ一覧"><p class="side-h">13業界</p><ul>{items}</ul></nav>'


def shell(current, title, desc, sections, main):
    full = SITE if current == 'index' else f'{title}｜{SITE}'
    if current not in ('yougo', 'about', 'privacy'):
        used = set()
        main = gloss_link(main, used) + gloss_data(used)
    url = '' if current == 'index' else f'{current}.html'
    extra_head = ''
    if SEARCH_CONSOLE:
        extra_head += f'<meta name="google-site-verification" content="{SEARCH_CONSOLE}">\n'
    if ADSENSE_CLIENT:
        extra_head += (f'<meta name="google-adsense-account" content="{ADSENSE_CLIENT}">\n'
                       f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}" crossorigin="anonymous"></script>\n')
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{html.escape(full)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{BASE}{url}">
<meta property="og:url" content="{BASE}{url}">
{extra_head}<meta property="og:title" content="{html.escape(full)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="topbar">
  <a class="brand" href="index.html">{SITE}<small>就活・志望動機用</small></a>
  <button type="button" class="menu-btn" id="menu-btn" aria-controls="side" aria-expanded="false">業界一覧</button>
</header>
<div class="layout">
{sidebar(current, sections)}
<main class="main">
{main}
<footer class="foot">
  <p class="warn"><strong>注意</strong>：数字は各ページに書いた出典の時点のものです。面接で使う前に、必ず最新の決算資料で確認してください。</p>
  <p class="asof">{ASOF}の情報をもとに作成</p>
  <p class="ad-note">このサイトは広告を掲載しています。紹介料を受け取るリンクには「PR」と表示します。</p>
  <nav class="foot-links" aria-label="サイトについて"><a href="about.html">運営者・お問い合わせ</a><a href="privacy.html">プライバシーポリシー・免責事項</a></nav>
</footer>
</main>
</div>
<script src="assets/app.js"></script>
</body>
</html>
'''


def page_html(p, i):
    secs = [(s['id'], s['nav']) for s in p['sections']] + [('soudan', '無料の相談先'), ('sources', '出典')]
    toc = ''.join(f'<a href="#{i_}">{n}</a>' for i_, n in secs)
    body = ''
    for n, s in enumerate(p['sections'], 1):
        inner = ''.join(block(b, p) for b in s['blocks'])
        body += (f'<section id="{s["id"]}" class="sec"><div class="sec-h"><span class="sec-no">{n:02d}</span>'
                 f'<h2>{md(s["title"])}</h2></div>{say(p["id"], s["id"])}{inner}</section>')
    body += soudan_sec(f'{len(p["sections"]) + 1:02d}')
    src = ''.join(f'<li><a href="{html.escape(u)}" target="_blank" rel="noopener">{md(t)}</a></li>' for t, u in p['sources'])
    body += f'<section id="sources" class="sec"><div class="sec-h"><span class="sec-no">出典</span><h2>出典</h2></div><ul class="sources">{src}</ul></section>'
    prev = PAGES[i - 1] if i > 0 else None
    nxt = PAGES[i + 1] if i < len(PAGES) - 1 else None
    pn = '<nav class="pager" aria-label="前後の業界">'
    pn += (f'<a class="prev" href="{prev["id"]}.html"><small>前の業界</small>{short(prev)}</a>' if prev
           else '<a class="prev" href="index.html"><small>戻る</small>総まとめ</a>')
    pn += (f'<a class="next" href="{nxt["id"]}.html"><small>次の業界</small>{short(nxt)}</a>' if nxt
           else '<a class="next" href="index.html"><small>戻る</small>総まとめ</a>')
    pn += '</nav>'
    main = (f'<header class="hero"><p class="crumb"><a href="index.html">総まとめ</a> › {i + 1:02d} / 13</p>'
            f'<h1>{md(p["title"])}</h1><p class="catch"><span class="mark">{md(p["catch"])}</span></p>'
            f'<p class="lead">{md(p["lead"])}</p><p class="gl-hint">点線の言葉を押すと、やさしい説明が出ます。まとめて読むなら<a href="yougo.html">用語集</a>へ。</p>'
            f'<nav class="toc" aria-label="このページの目次">{toc}</nav></header>{chara_card(p["id"])}{body}{pn}')
    return shell(p['id'], p['title'], p['lead'][:110], secs, main)


def index_html():
    secs = [('waves', '5つの波'), ('list', '業界一覧'), ('companies', '40社の有報'), ('howto', '使い方'), ('soudan', '無料の相談先')]
    waves = ''.join(
        f'<article class="wave"><h3>{md(n)}</h3><p>{md(w)}</p>{tsumari(TS.WAVES[j])}'
        f'<div class="w up"><span class="lbl">追い風の業界</span><p>{md(u)}</p></div>'
        f'<div class="w down"><span class="lbl">逆風の業界</span><p>{md(d)}</p></div></article>' for j, (n, w, u, d) in enumerate(IX.WAVES))
    label = {'up': '追い風', 'down': '逆風', 'both': '両面'}
    mrows = ''
    for p in PAGES:
        cells = ''
        for k in range(5):
            v = IX.MATRIX.get(p['id'], {}).get(k)
            cells += (f'<td title="{html.escape(v[1])}"><span class="tag {v[0]}">{label[v[0]]}</span><small>{md(v[1])}</small></td>'
                      if v else '<td></td>')
        mrows += f'<tr><th scope="row"><a href="{p["id"]}.html">{short(p)}</a></th>{cells}</tr>'
    matrix = (f'<div class="tbl matrix-wrap"><table class="matrix"><thead><tr><th scope="col">業界</th>'
              + ''.join(f'<th scope="col">{w}</th>' for w in IX.MATRIX_WAVES) + f'</tr></thead><tbody>{mrows}</tbody></table></div>'
              '<div class="legend"><span><span class="tag up">追い風</span> 稼ぎやすくなる</span><span><span class="tag down">逆風</span> 苦しくなる</span>'
              '<span><span class="tag both">両面</span> 良い面と悪い面がある</span><span>空欄は影響が小さい組み合わせ</span></div>')
    cards = ''.join(f'<a class="ind-card" href="{p["id"]}.html" style="--h:{CHARA[p["id"]]["hue"]}">'
                    f'<span class="ic-head">{seal(CHARA[p["id"]], "sm")}<span class="ic-who"><span class="ic-no">{i:02d}</span>'
                    f'<span class="ic-name">{md(CHARA[p["id"]]["name"])}</span><span class="ic-role">{md(CHARA[p["id"]]["role"])}</span></span></span><b>{short(p)}</b>'
                    f'<span class="ic-catch">{md(p["catch"])}</span><span class="ic-kw">{md(p["keywords"])}</span></a>'
                    for i, p in enumerate(PAGES, 1))
    yuho5 = ''.join(f'<li><span class="where">{md(a)}<small>{md(b)}</small></span><span class="use">{md(c)}</span></li>' for a, b, c in IX.YUHO5)
    howto = ''.join(f'<li>{md(t)}</li>' for t in IX.HOWTO)
    main = f'''
<header class="hero home">
  <p class="crumb">{ASOF}</p>
  <h1>業界研究ガイド<small>就活・志望動機用</small></h1>
  <p class="lead">{md(IX.LEAD)}</p>
  <p class="gl-hint">点線の言葉を押すと、やさしい説明が出ます。「政策金利って何？」から始めたい人は<a href="yougo.html">やさしい用語集</a>へ。</p>
  <nav class="toc" aria-label="このページの目次">{''.join(f'<a href="#{i}">{n}</a>' for i, n in secs)}</nav>
</header>
<section id="waves" class="sec"><div class="sec-h"><span class="sec-no">01</span><h2>全業界に共通する5つの波（2026年）</h2></div>
  <div class="waves">{waves}</div>
  <h3 class="sub">業界ごとの早見表</h3>
  <p class="note">各業界ページの内容をもとに、5つの波がその業界にどう効いているかを1枚にしました。業界名を押すとそのページへ移ります。</p>
  {matrix}
</section>
<section id="list" class="sec"><div class="sec-h"><span class="sec-no">02</span><h2>業界一覧</h2></div>
  <p>13の業界それぞれに、業界の性格をそのまま人にしたキャラクターがいます。各ページでは、そのキャラが「キミの毎日のどこにいるか」から案内します。</p>
  <div class="ind-grid">{cards}</div>
</section>
<section id="companies" class="sec"><div class="sec-h"><span class="sec-no">03</span><h2>40社の有価証券報告書を横に並べると</h2></div>
  <p>各ページの「有価証券報告書で比べる」では、業界ごとに主要2〜6社、合計40社の最新の有価証券報告書（2026年提出）を実際に読み込みました。ここでは業界をまたいで並べます。</p>
  <div class="callout"><strong>ROE（自己資本利益率）とは？</strong><p>株主から預かったお金100円を使って、1年で何円の利益を出したかを表す数字です。ROE10%なら100円で10円稼いだことになります。日本では「<span class="mark">8%を超えるのが目安</span>」とよく言われます。</p></div>
  {chart(IX.ROE)}
  <h3 class="sub">業界をまたいで見えたこと</h3>
  {finds(IX.FINDS)}
  <h3 class="sub">有報の読み方：最初に見る5か所</h3>
  <p>有報は100ページを超えますが、志望動機づくりなら次の5か所で十分です。<a href="https://disclosure2.edinet-fsa.go.jp/" target="_blank" rel="noopener">EDINET</a>（金融庁のサイト）で会社名を検索すると無料で読めます。</p>
  <ol class="yuho5">{yuho5}</ol>
</section>
<section id="howto" class="sec"><div class="sec-h"><span class="sec-no">04</span><h2>このガイドの使い方</h2></div>
  <ol class="howto">{howto}</ol>
</section>
{soudan_sec('05')}
<nav class="pager" aria-label="最初の業界"><span></span><a class="next" href="{PAGES[0]["id"]}.html"><small>最初の業界から読む</small>{short(PAGES[0])}</a></nav>'''
    return shell('index', SITE, '13業界の仕事と稼ぎ方・2026年の動き・志望動機の作り方を、有価証券報告書とニュースの出典つきでまとめた就活用の業界研究ガイド。', secs, main)


def about_html():
    main = f'''
<header class="hero"><p class="crumb"><a href="index.html">総まとめ</a> › サイトについて</p><h1>運営者・お問い合わせ</h1></header>
<section id="who" class="sec"><div class="sec-h"><span class="sec-no">01</span><h2>運営者</h2></div>
  <dl class="kv"><div><dt>サイト名</dt><dd>{SITE}（就活・志望動機用）</dd></div><div><dt>運営者</dt><dd>rei</dd></div><div><dt>作った理由</dt><dd>自分と友達・後輩の業界研究のため。ニュースと各社の有価証券報告書を読み、同じ型で13業界を整理しました。</dd></div><div><dt>情報の時点</dt><dd>{ASOF}。数字の出典は各ページの最後にあります。</dd></div></dl>
</section>
<section id="contact" class="sec"><div class="sec-h"><span class="sec-no">02</span><h2>お問い合わせ</h2></div>
  <p>内容の誤り、古くなった数字、掲載についてのご連絡はこちらからお願いします。</p>
  <p class="sent-msg" id="sent-msg" hidden>送信しました。ありがとうございます。</p>
  <form class="contact" action="https://api.web3forms.com/submit" method="POST">
    <input type="hidden" name="access_key" value="{WEB3FORMS_KEY}">
    <input type="hidden" name="subject" value="【業界研究ガイド】お問い合わせ">
    <input type="hidden" name="redirect" value="{BASE}about.html?sent=1#contact">
    <input type="checkbox" name="botcheck" tabindex="-1" autocomplete="off" hidden>
    <label>お名前<input type="text" name="name" required autocomplete="name"></label>
    <label>メールアドレス<input type="email" name="email" required autocomplete="email"></label>
    <label>内容<textarea name="message" rows="6" required></textarea></label>
    <button type="submit" class="btn">送信する</button>
  </form>
</section>'''
    return shell('about', '運営者・お問い合わせ', f'{SITE}の運営者情報とお問い合わせ先。', [('who', '運営者'), ('contact', 'お問い合わせ')], main)


def privacy_html():
    items = [
        ('広告について', ['このサイトは、第三者配信の広告サービス「Google アドセンス」を利用しています。',
                     'Google などの広告配信事業者は、Cookie を使って、このサイトや他のサイトへの過去のアクセス情報に基づいて広告を表示することがあります。'
                     'パーソナライズ広告は [Google の広告設定](https://adssettings.google.com/) で無効にできます。'
                     'Cookie の扱いについては [Google のポリシーと規約](https://policies.google.com/technologies/ads?hl=ja) をご覧ください。']),
        ('紹介リンク（アフィリエイト）について', ['ページ内で紹介するサービスの一部には、紹介料を受け取るリンクを含むことがあります。その場合は「PR」と表示します。',
                     '紹介するのは、学生が無料で使えて、人に相談できるサービスに限ります。紹介料の有無で内容や順番を変えることはありません。']),
        ('アクセス解析について', ['今後、アクセス数を把握するために Google アナリティクスを使う場合があります。データは Cookie を使って匿名で集められ、個人を特定するものではありません。']),
        ('お問い合わせで受け取る情報', ['お問い合わせフォームで受け取ったお名前・メールアドレスは、返信のためだけに使い、第三者に渡すことはありません。法令に基づく場合を除きます。',
                     'フォームの送信には Web3Forms を利用しています。']),
        ('免責事項', ['数字や出来事は、各ページに書いた出典の時点のものです。できるかぎり正確にしていますが、内容を保証するものではありません。',
                     '就職活動の判断は、必ず各社の最新の決算資料・採用ページで確認したうえで、ご自身で行ってください。このサイトの情報によって生じた損害について、運営者は責任を負いません。',
                     'リンク先のサイトの内容については、各運営者にお問い合わせください。']),
        ('著作権', ['文章・図・イラストの著作権は運営者にあります。引用する場合は出典としてこのサイトへのリンクを付けてください。各社のロゴや社名は、それぞれの会社の商標です。']),
    ]
    body = ''
    for n, (h, ps) in enumerate(items, 1):
        body += (f'<section id="p{n}" class="sec"><div class="sec-h"><span class="sec-no">{n:02d}</span><h2>{h}</h2></div>'
                 + ''.join(f'<p>{md(x)}</p>' for x in ps) + '</section>')
    main = (f'<header class="hero"><p class="crumb"><a href="index.html">総まとめ</a> › サイトについて</p>'
            f'<h1>プライバシーポリシー・免責事項</h1><p class="lead">制定：2026年10月25日</p></header>{body}')
    return shell('privacy', 'プライバシーポリシー・免責事項', f'{SITE}のプライバシーポリシー・広告・免責事項。',
                 [(f'p{n}', h) for n, (h, _) in enumerate(items, 1)], main)


def gloss_card(g):
    rows = [('ひとことで', g['short'])]
    if g.get('iikae'): rows.append(('友達に説明するなら', g['iikae']))
    if g.get('tatoe'): rows.append(('たとえると', g['tatoe']))
    if g.get('kankaku'): rows.append(('数字の感覚', g['kankaku']))
    if g.get('up'): rows.append(g['up'])
    if g.get('down'): rows.append(g['down'])
    dl = ''.join(f'<div><dt>{md(a)}</dt><dd>{md(b)}</dd></div>' for a, b in rows)
    yomi = f'<small>{md(g["yomi"])}</small>' if g.get('yomi') else ''
    link = f'<a class="gc-link" href="{g["link"][1]}">{md(g["link"][0])}</a>' if g.get('link') else ''
    words = html.escape(' '.join([g['t']] + g['al'] + [g.get('yomi', '')]), quote=True)
    return (f'<article class="gcard" id="g-{g["k"]}" data-words="{words}"><h3>{md(g["t"])}{yomi}</h3>'
            f'<dl>{dl}</dl>{link}</article>')


def yougo_html():
    secs = [(f'cat{i}', c) for i, c in enumerate(GCATS, 1)]
    body = ''
    for i, c in enumerate(GCATS, 1):
        cards = ''.join(gloss_card(g) for g in GLOSS if g['cat'] == c)
        body += (f'<section id="cat{i}" class="sec"><div class="sec-h"><span class="sec-no">{i:02d}</span><h2>{c}</h2></div>'
                 f'<div class="gcards">{cards}</div></section>')
    main = (f'<header class="hero"><p class="crumb"><a href="index.html">総まとめ</a> › 用語集</p>'
            f'<h1>やさしい用語集</h1>'
            f'<p class="lead">ニュースや有価証券報告書に出てくる言葉を、{len(GLOSS)}語、ふつうの言葉で説明します。'
            f'「ひとことで」「友達に説明するなら」「数字の感覚」まで読めば、面接で自分の言葉で言い換えられます。</p>'
            f'<label class="gfind"><span>言葉で探す</span><input type="search" id="gfind" placeholder="例：金利、ROE、関税" autocomplete="off"></label>'
            f'<p class="note" id="gfind-none" hidden>見つかりませんでした。別の書き方でも試してみてください。</p>'
            f'<nav class="toc" aria-label="分類">{"".join(f"<a href=#{i_}>{n}</a>" for i_, n in secs)}</nav></header>{body}')
    return shell('yougo', 'やさしい用語集', f'政策金利・ROE・関税・有価証券報告書など、就活の業界研究で出てくる{len(GLOSS)}語を、大学生にも分かる言葉と数字の感覚で説明する用語集。', secs, main)


def sitemap():
    urls = ['', 'yougo.html'] + [f'{p["id"]}.html' for p in PAGES] + ['about.html', 'privacy.html']
    body = ''.join(f'<url><loc>{BASE}{u}</loc><lastmod>2026-10-25</lastmod></url>' for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'assets').mkdir(parents=True)
    for f in (ROOT / 'assets').iterdir():
        if f.is_dir():
            shutil.copytree(f, OUT / 'assets' / f.name)
        else:
            shutil.copy(f, OUT / 'assets' / f.name)
    (OUT / 'index.html').write_text(index_html(), encoding='utf-8')
    for i, p in enumerate(PAGES):
        (OUT / f'{p["id"]}.html').write_text(page_html(p, i), encoding='utf-8')
    (OUT / '.nojekyll').write_text('')
    (OUT / 'yougo.html').write_text(yougo_html(), encoding='utf-8')
    (OUT / 'about.html').write_text(about_html(), encoding='utf-8')
    (OUT / 'privacy.html').write_text(privacy_html(), encoding='utf-8')
    (OUT / 'sitemap.xml').write_text(sitemap(), encoding='utf-8')
    print(f'{len(PAGES) + 1} ページを書き出しました → {OUT}')


if __name__ == '__main__':
    main()
