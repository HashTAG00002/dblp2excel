from __future__ import annotations

import os
import certifi
import pandas as pd
import requests
from lxml import html
from requests.adapters import HTTPAdapter
from tqdm.auto import tqdm
from urllib3.util.retry import Retry

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

confs = [
    "aaai", # 8.2
    "ndss", # 4.23 & 8.7
    "iclr", # 10.2
    "www", # 10.7
    "naacl", # 10.16
    "sp", # 6.6 & 11.14
    "cvpr", # 11.15


    "ijcai", # 1.24
    "siggraph", # 1.24
    "icml", # 1.31
    "uss", # 8.27 & 2.3
    "acl", # 2.16
    "eccv", # 3.8
    "iccv", # 3.8
    "mm", # 4.12
    "ccs", # 1.9 & 4.15
    "nips", # 5.16
    "emnlp", # 5.20
    "siggrapha", # 5.24
    "ijcv",
    "jmlr",
    "pami",
    "tip",
    "tifs",
    ]
years = ["2018","2019","2020","2021","2022","2023","2024","2025"]
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
    print("🔍  Fetching HTML page …")
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
    print(f"✅  Downloaded {size_kb} KB")
    return resp.content

def parse_titles(page_content: bytes) -> list[str]:
    """Extract all titles via XPath and show tqdm bar."""
    print("📝  Parsing titles …")
    #print(page_content)
    parser = html.HTMLParser(no_network=True, huge_tree=True) 
    tree = html.fromstring(page_content, parser=parser)
    title_nodes = tree.xpath('//span[@class="title"]')

    titles: list[str] = []
    for node in tqdm(title_nodes, desc="Extracting", unit="title", ncols=80):
        title_text = " ".join(node.itertext()).strip()
        titles.append(title_text)

    print(f"✅  Parsed {len(titles)} titles")
    return titles

def save_excel(titles: list[str], outfile: str, name: str) -> None:
    print(f"💾 {name} Writing / appending Excel …")
    new_df = pd.DataFrame({
        "Conference/Journal": [name] * len(titles),
        "Title"     : titles,
    })

    if os.path.exists(outfile):
        old_df = pd.read_excel(outfile)
        combined = pd.concat([old_df, new_df], ignore_index=True)
    else:
        combined = new_df

    combined.to_excel(outfile, index=False)
    print(f"✅  Saved {len(new_df)} rows → {outfile}  (total {len(combined)})\n")


def main() -> None:
    if os.path.exists(OUTFILE):
        os.remove(OUTFILE)
    for year in years:
        for conf in confs:
            if conf == "iccv" and int(year) % 2 == 0:
                continue
            if conf == "eccv" and int(year) % 2 == 1:
                continue
            if conf == "eccv":
                titles = []
                part = 1
                name = f"{conf}{year}"
                while True:
                    URL = f"https://dblp.org/db/conf/{conf}/{conf}{year}-{part}.html"
                    try:
                        page_content = fetch_page(URL)
                    except:   # ← 关键：404 时正常退出
                        print(f"❌  {URL} does not exist!")
                        break
                    titles.extend(parse_titles(page_content)[1:])
                    part += 1
                if part == 1:
                    continue
            else:
                begin_index = 1
                if conf == "tifs" or conf == "tip" or conf == "pami" or conf == "ijcv":
                    URL = f"https://dblp.org/db/journals/{conf}/{conf}{str(int(year)-start_year[conf])}.html"
                    begin_index = 0
                elif conf == "nips" and int(year) >= 2020:
                    URL = f"https://dblp.org/db/conf/{conf}/neurips{year}.html"
                else:
                    URL = f"https://dblp.org/db/conf/{conf}/{conf}{year}.html"
                name = f"{conf}{year}"

                try:
                    page_content = fetch_page(URL)
                except:   # ← 关键：404 时正常退出
                    print(f"❌  {URL} does not exist!")
                    continue
                titles = parse_titles(page_content)[begin_index:]
            
            save_excel(titles, OUTFILE, name)
    
    print("🎉  All done. Enjoy your spreadsheets!")


if __name__ == "__main__":
    main()
