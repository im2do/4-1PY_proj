# -*- coding: utf-8 -*-
"""
워드클라우드 7종 생성 — KPop Demon Hunters 리뷰
=================================================
입력(빈도 CSV, word,count):
  watcha/data/freq_positive.csv     (한국어 긍정)
  watcha/data/freq_negative.csv     (한국어 부정)
  watcha/data/freq_all.csv          (한국어 종합)
  letterboxd/data/freq_positive.csv (영어 긍정)
  letterboxd/data/freq_negative.csv (영어 부정)
  letterboxd/data/freq_all.csv      (영어 종합)

출력(wordclouds/, 각 1600x900 고해상):
  1 watcha_positive.png   2 watcha_negative.png   3 watcha_all.png
  4 letterboxd_positive.png 5 letterboxd_negative.png 6 letterboxd_all.png
  7 total.png  (한국어 종합 + 영어 종합 합산)

설치: pip install wordcloud matplotlib
"""
from __future__ import annotations
import csv, os
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from wordcloud import WordCloud

# ---------------------------------------------------------------------------
# 경로 / 폰트
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)              # outputs/
WATCHA = os.path.join(ROOT, "watcha", "data")
LBX    = os.path.join(ROOT, "letterboxd", "data")
OUT    = BASE
os.makedirs(OUT, exist_ok=True)

# 한글 렌더링용 폰트(한글+영문 모두 표시 가능 → 모든 클라우드에 사용)
FONT_CANDIDATES = [
    os.path.expanduser("~/.fonts/NanumSquareRoundR.ttf"),
    os.path.join(ROOT, "work/extracted/python-tutorial-main/06_web_scraping/NanumSquareRoundR.ttf"),
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]
FONT = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
if FONT is None:
    # koreanize_matplotlib 번들 폰트 fallback
    import koreanize_matplotlib  # noqa
    FONT = font_manager.findfont("NanumGothic")
font_manager.fontManager.addfont(FONT)
plt.rcParams["font.family"] = font_manager.FontProperties(fname=FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False

# 캔버스 크기(너무 작지 않게)
W, H = 1600, 900


def load_freq(path: str) -> dict[str, int]:
    freq = {}
    with open(path, encoding="utf-8-sig") as f:
        r = csv.reader(f)
        next(r, None)  # 헤더
        for row in r:
            if len(row) < 2:
                continue
            try:
                freq[row[0]] = int(row[1])
            except ValueError:
                pass
    return freq


def make_cloud(freq: dict, title: str, fname: str, colormap: str) -> None:
    if not freq:
        print(f"  (건너뜀: 빈 데이터) {fname}")
        return
    wc = WordCloud(
        font_path=FONT, width=W, height=H,
        background_color="white", max_words=200,
        colormap=colormap, prefer_horizontal=0.92,
        relative_scaling=0.35, min_font_size=10, collocations=False,
    ).generate_from_frequencies(freq)

    plt.figure(figsize=(16, 9.6))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.title(title, fontsize=26, fontweight="bold", pad=16)
    plt.tight_layout(pad=0.6)
    out = os.path.join(OUT, fname)
    plt.savefig(out, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  saved {fname}  (단어 {len(freq)})")


def main() -> None:
    # 6개 빈도 로드
    wc_pos = load_freq(os.path.join(WATCHA, "freq_positive.csv"))
    wc_neg = load_freq(os.path.join(WATCHA, "freq_negative.csv"))
    wc_all = load_freq(os.path.join(WATCHA, "freq_all.csv"))
    lb_pos = load_freq(os.path.join(LBX, "freq_positive.csv"))
    lb_neg = load_freq(os.path.join(LBX, "freq_negative.csv"))
    lb_all = load_freq(os.path.join(LBX, "freq_all.csv"))

    # 7) 전체 총합 = 한국어 종합 + 영어 종합
    total = Counter(wc_all) + Counter(lb_all)

    print("[워드클라우드 생성]")
    make_cloud(wc_pos, "왓챠 한국어 리뷰 · 긍정 (Positive)",      "1_watcha_positive.png",     "summer")
    make_cloud(wc_neg, "왓챠 한국어 리뷰 · 부정 (Negative)",      "2_watcha_negative.png",     "autumn")
    make_cloud(wc_all, "왓챠 한국어 리뷰 · 종합 (All)",           "3_watcha_all.png",          "viridis")
    make_cloud(lb_pos, "Letterboxd English · Positive",        "4_letterboxd_positive.png", "summer")
    make_cloud(lb_neg, "Letterboxd English · Negative",        "5_letterboxd_negative.png", "autumn")
    make_cloud(lb_all, "Letterboxd English · All",             "6_letterboxd_all.png",      "viridis")
    make_cloud(dict(total), "전체 총합 · 한국어+영어 (Total)",   "7_total.png",               "plasma")
    print("[완료] outputs/wordclouds/ 에 7개 PNG 생성")


if __name__ == "__main__":
    main()
