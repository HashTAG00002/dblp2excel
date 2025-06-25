from __future__ import annotations
import os, certifi, pandas as pd, requests
from lxml import html
from requests.adapters import HTTPAdapter
from tqdm.auto import tqdm
from urllib3.util.retry import Retry

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

confs = [
    "ijcv",
    "jmlr",
    "pami",
    "tip",
    "tifs",
    "aaai", # 8.2
    "ndss", # 4.23 & 8.7 0
    "iclr", # 10.2 0
    "www", # 10.7
    "naacl", # 10.16
    "sp", # 6.6 & 11.14 0
    "cvpr", # 11.15 0


    "ijcai", # 1.24
    # "siggraph", # 1.24
    "icml", # 1.31
    "uss", # 8.27 & 2.3
    "acl", # 2.16
    "eccv", # 3.8
    "iccv", # 3.8 0
    "mm", # 4.12
    "ccs", # 1.9 & 4.15
    "nips", # 5.16
    "emnlp", # 5.20
    # "siggrapha", # 5.24
    ]

conf_begin_with0 = {"ndss", "iclr", "sp", "cvpr", "iccv"}

confs_full = [
    "IJCV",
    "JMLR",
    "TPAMI",
    "TIP",
    "TIFS",
    "AAAI", # 8.2
    "NDSS", # 4.23 & 8.7
    "ICLR", # 10.2
    "WWW", # 10.7
    "NAACL", # 10.16
    "S&P", # 6.6 & 11.14
    "CVPR", # 11.15


    "IJCAI", # 1.24
    # "SIGGRAPH", # 1.24
    "ICML", # 1.31
    "USENIX Security", # 8.27 & 2.3
    "ACL", # 2.16
    "ECCV", # 3.8
    "ICCV", # 3.8
    "ACM MM", # 4.12
    "CCS", # 1.9 & 4.15
    "NeurIPS", # 5.16
    "EMNLP", # 5.20
    # "SIGGRAPH Asia", # 5.24
    ]

years = ["2018","2019","2020","2021","2022"]
start_year = {
    "pami": 1978,
    "tip": 1991,
    "jmlr": 1999,
    "tifs": 2005,
    "ijcv": 1892
}

TIMEOUT = 10  # seconds
MAX_RETRIES = 5
BACKOFF_FACTOR = 0.5
OUTFILE = "./all_papers.xlsx"

def fetch_page(url: str) -> bytes:
    """Download HTML with automatic retries and return raw bytes."""
    print(f"🔍  Fetching {url} …")
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))

    resp = session.get(url, timeout=TIMEOUT, verify=certifi.where())
    resp.raise_for_status()
    size_kb = len(resp.content) // 1024
    print(f"✅  Downloaded {size_kb} KB")
    return resp.content

def parse_titles_authors(page: bytes) -> tuple[list[str],list[str]]:
    """Return (titles, authors) lists; skip Frontmatter / empty-author items."""
    print("📝  Parsing titles …")

    parser = html.HTMLParser(no_network=True, huge_tree=True)
    tree   = html.fromstring(page, parser=parser)

    entries = tree.xpath('//li[contains(@class,"entry")]')
    titles, authors = [], []

    for li in tqdm(entries, desc="Extracting", unit="pub", ncols=80):
        # ---- 题名：用 //text() 收集后代所有文本 ----
        title = " ".join(li.xpath('.//span[@class="title"]//text()')).strip()
        if not title or title.lower().startswith(("frontmatter", "editorial")):
            continue

        # ---- 作者：限定在 <cite>，避免抓到导航里的重复链接 ----
        names = li.xpath('.//cite//span[@itemprop="author"]'
                         '//span[@itemprop="name"]/text()')
        if not names:                 # 无作者条目直接略过
            continue

        titles.append(title)
        authors.append("; ".join(n.strip() for n in names))

    print(f"✅  Parsed {len(titles)} valid items")
    return titles, authors


# ---------------------- Excel writer -----------------------
def append_sheet(df:pd.DataFrame, year:str)->None:
    mode = "a" if os.path.exists(OUTFILE) else "w"
    with pd.ExcelWriter(OUTFILE, engine="openpyxl", mode=mode) as writer:
        df.to_excel(writer, sheet_name=year, index=False)
    print(f"💾  {len(df)} rows → sheet [{year}]")


def main() -> None:
    if os.path.exists(OUTFILE):
        os.remove(OUTFILE)
    for year in years[::-1]:
        for conf,conf_full in zip(confs[::-1],confs_full[::-1]):
            yearly_rows = []
            if conf == "iccv" and int(year) % 2 == 0:
                continue
            titles, authors = [], []

            # ---------- a) ECCV 分卷 ----------
            if conf == "eccv":
                if int(year) % 2 == 1:
                    continue
                part = 1
                while True:
                    URL = f"https://dblp.org/db/conf/{conf}/{conf}{year}-{part}.html"
                    try:
                        page = fetch_page(URL)
                    except:   # ← 关键：404 时正常退出
                        print(f"❌  {URL} does not exist!")
                        break
                    t,a  = parse_titles_authors(page)
                    if not t: break
                    titles.extend(t[1:]); authors.extend(a[1:])
                    part += 1
                if part == 1:
                    continue

            # ---------- b) 期刊卷号 ----------
            elif conf in {"tifs", "tip", "pami", "ijcv", "jmlr"}:
                vol  = int(year) - start_year[conf]
                url  = f"https://dblp.org/db/journals/{conf}/{conf}{vol}.html"
                try:
                    page = fetch_page(url)
                except Exception:
                    continue
                titles, authors = parse_titles_authors(page)


            # ---------- c) 常规 + “‑1” 双尝试 ----------
            else:
                base = f"https://dblp.org/db/conf/{conf}/{conf}{year}.html"
                if conf=="nips" and int(year)>=2020:
                    base = f"https://dblp.org/db/conf/{conf}/neurips{year}.html"
                
                try_url = [base]
                if conf in {"acl","naacl","emnlp"}:
                    try_url.append(base.replace(f"{year}.html", f"{year}-1.html"))
                for url in try_url:
                    try:
                        page = fetch_page(url)
                        titles, authors = parse_titles_authors(page)
                        if not conf in conf_begin_with0:
                            titles = titles[1:]; authors = authors[1:]
                        if titles:
                            break
                    except Exception:
                        continue

            if not titles:
                continue

            yearly_rows.extend({
                "Conference/Journal": f"{conf_full}{year}",
                "Title" : t,
                "Authors": au
            } for t,au in zip(titles,authors))

            # ==== 写入本年度工作表 ====
            if yearly_rows:
                append_sheet(pd.DataFrame(yearly_rows), f"{conf_full}{year}")
    
    print("🎉  All done. Enjoy your spreadsheets!")


if __name__ == "__main__":
    main()
