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

ROOT = Path(__file__).parent
OUT = ROOT / 'docs'
PAGES = [FINANCE, TRADING, CONSULTING, IT, AUTO, ELECTRONICS, MATERIALS, FOOD, REALESTATE, INFRA, MEDIA, TRAVEL, HR]
SITE = '業界研究ガイド'
ASOF = '2026年10月21日時点'


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


def news(items):
    out = ''
    for i, (title, paras) in enumerate(items, 1):
        body = ''.join(f'<p>{md(p)}</p>' for p in paras)
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
    if t == 'news': return news(b[1])
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


# ---------- 枠 ----------
def sidebar(current, sections):
    items = f'<li><a href="index.html"{" aria-current=page" if current == "index" else ""}>総まとめ</a>'
    if current == 'index':
        items += '<ul>' + ''.join(f'<li><a href="#{i}">{n}</a></li>' for i, n in sections) + '</ul>'
    items += '</li>'
    for p in PAGES:
        cur = p['id'] == current
        items += f'<li><a href="{p["id"]}.html"{" aria-current=page" if cur else ""}>{short(p)}</a>'
        if cur:
            items += '<ul>' + ''.join(f'<li><a href="#{i}">{n}</a></li>' for i, n in sections) + '</ul>'
        items += '</li>'
    return f'<nav class="side" id="side" aria-label="ページ一覧"><p class="side-h">13業界</p><ul>{items}</ul></nav>'


def shell(current, title, desc, sections, main):
    full = SITE if current == 'index' else f'{title}｜{SITE}'
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{html.escape(full)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="robots" content="noindex">
<meta property="og:title" content="{html.escape(full)}">
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
</footer>
</main>
</div>
<script src="assets/app.js"></script>
</body>
</html>
'''


def page_html(p, i):
    secs = [(s['id'], s['nav']) for s in p['sections']] + [('sources', '出典')]
    toc = ''.join(f'<a href="#{i_}">{n}</a>' for i_, n in secs)
    body = ''
    for n, s in enumerate(p['sections'], 1):
        inner = ''.join(block(b, p) for b in s['blocks'])
        body += (f'<section id="{s["id"]}" class="sec"><div class="sec-h"><span class="sec-no">{n:02d}</span>'
                 f'<h2>{md(s["title"])}</h2></div>{inner}</section>')
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
            f'<p class="lead">{md(p["lead"])}</p>'
            f'<nav class="toc" aria-label="このページの目次">{toc}</nav></header>{body}{pn}')
    return shell(p['id'], p['title'], p['lead'][:110], secs, main)


def index_html():
    secs = [('waves', '5つの波'), ('list', '業界一覧'), ('companies', '40社の有報'), ('howto', '使い方')]
    waves = ''.join(
        f'<article class="wave"><h3>{md(n)}</h3><p>{md(w)}</p>'
        f'<div class="w up"><span class="lbl">追い風の業界</span><p>{md(u)}</p></div>'
        f'<div class="w down"><span class="lbl">逆風の業界</span><p>{md(d)}</p></div></article>' for n, w, u, d in IX.WAVES)
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
    cards = ''.join(f'<a class="ind-card" href="{p["id"]}.html"><span class="ic-no">{i:02d}</span><b>{short(p)}</b>'
                    f'<span class="ic-catch">{md(p["catch"])}</span><span class="ic-kw">{md(p["keywords"])}</span></a>'
                    for i, p in enumerate(PAGES, 1))
    yuho5 = ''.join(f'<li><span class="where">{md(a)}<small>{md(b)}</small></span><span class="use">{md(c)}</span></li>' for a, b, c in IX.YUHO5)
    howto = ''.join(f'<li>{md(t)}</li>' for t in IX.HOWTO)
    main = f'''
<header class="hero home">
  <p class="crumb">{ASOF}</p>
  <h1>業界研究ガイド<small>就活・志望動機用</small></h1>
  <p class="lead">{md(IX.LEAD)}</p>
  <nav class="toc" aria-label="このページの目次">{''.join(f'<a href="#{i}">{n}</a>' for i, n in secs)}</nav>
</header>
<section id="waves" class="sec"><div class="sec-h"><span class="sec-no">01</span><h2>全業界に共通する5つの波（2026年）</h2></div>
  <div class="waves">{waves}</div>
  <h3 class="sub">業界ごとの早見表</h3>
  <p class="note">各業界ページの内容をもとに、5つの波がその業界にどう効いているかを1枚にしました。業界名を押すとそのページへ移ります。</p>
  {matrix}
</section>
<section id="list" class="sec"><div class="sec-h"><span class="sec-no">02</span><h2>業界一覧</h2></div>
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
  <nav class="pager" aria-label="最初の業界"><span></span><a class="next" href="{PAGES[0]["id"]}.html"><small>最初の業界から読む</small>{short(PAGES[0])}</a></nav>
</section>'''
    return shell('index', SITE, '13業界の仕事と稼ぎ方・2026年の動き・志望動機の作り方を、有価証券報告書とニュースの出典つきでまとめた就活用の業界研究ガイド。', secs, main)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'assets').mkdir(parents=True)
    for f in (ROOT / 'assets').iterdir():
        shutil.copy(f, OUT / 'assets' / f.name)
    (OUT / 'index.html').write_text(index_html(), encoding='utf-8')
    for i, p in enumerate(PAGES):
        (OUT / f'{p["id"]}.html').write_text(page_html(p, i), encoding='utf-8')
    (OUT / '.nojekyll').write_text('')
    (OUT / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    print(f'{len(PAGES) + 1} ページを書き出しました → {OUT}')


if __name__ == '__main__':
    main()
