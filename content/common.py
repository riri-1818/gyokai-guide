"""ページの中身で共通に使う小道具。"""

FY = ['2021年度', '2022年度', '2023年度', '2024年度', '2025年度']
NET_SUB = '親会社の株主に帰属する当期純利益（億円）。各社の有価証券報告書「主要な経営指標等の推移」より'


def E(code, name):
    """EDINET の有価証券報告書PDFへのリンク（[名前](URL) の形）。"""
    return f'[{name}](https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf/{code}.pdf)'


def net_chart(title, series, hl, caption):
    """各社の純利益（5期分）の折れ線グラフ。series は {会社名: [5期分の数字 or None]}。"""
    return {'type': 'line', 'title': title, 'sub': NET_SUB, 'x': FY, 'series': series, 'hl': hl,
            'unit': '億円', 'caption': caption}


YUHO_NOTE = ('会社名のリンクから、実際の有価証券報告書（PDF）を開けます。平均年収・平均年齢は有報の「従業員の状況」に載る'
             '**提出会社**の数字で、持株会社の場合は実際に多くの社員が働く会社とは異なります。')
YUHO_COLS = ['会社', '決算期', '売上規模（最新期）', 'ROE', '平均年収', '平均年齢']
GOAL_COLS = ['会社', '目標・重点（対処すべき課題より）', '主なリスク（事業等のリスクより）']
