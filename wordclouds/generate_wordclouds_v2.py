# -*- coding: utf-8 -*-
"""
워드클라우드 7종 (리파인 버전) — 절제된 에디토리얼 팔레트
- 따뜻한 오프화이트 배경(슬라이드와 동일) + 차분한 단색/듀오톤 색감
- 제목 텍스트는 슬라이드에서 달므로 이미지에는 넣지 않음(여백 확보)
- 폰트: NanumGothic (둥근 폰트 대신 정제된 고딕)
"""
import csv, os, random
import matplotlib; matplotlib.use("Agg")
from wordcloud import WordCloud

BASE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(BASE)
WATCHA = os.path.join(ROOT, "watcha", "data"); LBX = os.path.join(ROOT, "letterboxd", "data")
OUT = os.path.join(BASE, "refined"); os.makedirs(OUT, exist_ok=True)

FONT_CANDS = [
    os.path.expanduser("~/.local/lib/python3.10/site-packages/koreanize_matplotlib/fonts/NanumGothicBold.ttf"),
    "/sessions/charming-inspiring-bohr/.local/lib/python3.10/site-packages/koreanize_matplotlib/fonts/NanumGothicBold.ttf",
    os.path.expanduser("~/.fonts/NanumSquareRoundR.ttf"),
]
FONT = next((p for p in FONT_CANDS if os.path.exists(p)), None)

PAPER = "#F7F4EF"
W, H = 2000, 1150

# 팔레트(머트한 톤)
GREENS  = ["#3E6B4E", "#4E7D5A", "#5E8C66", "#6E9A73", "#34594155"[:7]]
GREENS  = ["#345941", "#3E6B4E", "#4E7D5A", "#5E8C66", "#6E9A73"]
CRIMSON = ["#7E2230", "#94283A", "#B23A48", "#C25461", "#A33645"]
MULTI   = ["#1C1B22", "#B23A48", "#A8842C", "#4E7D5A", "#445A6B", "#7A5C7E"]


def picker(palette):
    def f(word, **kw):
        random.seed(hash(word) & 0xffffffff)
        return random.choice(palette)
    return f


def load_freq(path):
    freq = {}
    with open(path, encoding="utf-8-sig") as fh:
        r = csv.reader(fh); next(r, None)
        for row in r:
            if len(row) >= 2:
                try: freq[row[0]] = int(row[1])
                except ValueError: pass
    return freq


def cloud(freq, fname, palette):
    if not freq:
        print("skip", fname); return
    wc = WordCloud(font_path=FONT, width=W, height=H, background_color=PAPER,
                   max_words=180, prefer_horizontal=0.95, relative_scaling=0.4,
                   min_font_size=11, margin=4, collocations=False,
                   color_func=picker(palette)).generate_from_frequencies(freq)
    out = os.path.join(OUT, fname); wc.to_file(out)
    print("saved", fname, len(freq))


from collections import Counter
wc_pos = load_freq(os.path.join(WATCHA, "freq_positive.csv"))
wc_neg = load_freq(os.path.join(WATCHA, "freq_negative.csv"))
wc_all = load_freq(os.path.join(WATCHA, "freq_all.csv"))
lb_pos = load_freq(os.path.join(LBX, "freq_positive.csv"))
lb_neg = load_freq(os.path.join(LBX, "freq_negative.csv"))
lb_all = load_freq(os.path.join(LBX, "freq_all.csv"))
total = dict(Counter(wc_all) + Counter(lb_all))

cloud(wc_pos, "1_watcha_positive.png",     GREENS)
cloud(wc_neg, "2_watcha_negative.png",     CRIMSON)
cloud(wc_all, "3_watcha_all.png",          MULTI)
cloud(lb_pos, "4_letterboxd_positive.png", GREENS)
cloud(lb_neg, "5_letterboxd_negative.png", CRIMSON)
cloud(lb_all, "6_letterboxd_all.png",      MULTI)
cloud(total,  "7_total.png",               MULTI)
print("done →", OUT)
