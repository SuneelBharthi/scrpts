import os
import re
import io
import json
import time
import random
import requests
from datetime import datetime
from typing import List, Dict, Optional, Set
import pandas as pd
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager
# ------------ CONFIG ------------
START_URL = (
    "https://www.ebay.com/sch/i.html?_dkr=1&iconV2Request=true&_blrs=recall_filtering"
    "&_ssn=galentech99&store_name=galenttech99&_oac=1&_ipg=240"
)
BASE_IMG_DIR = "Product's_Imgs"
HEADLESS = True
CHECKPOINT_EVERY = 2
# ------------ DRIVER ------------
def create_driver(headless: bool = False) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--ignore-certificate-errors")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"}
        )
    except Exception:
        pass
    return driver

# ------------ UTILS ------------
def wait_css(driver, css, sec=12):
    return WebDriverWait(driver, sec).until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))

def js_scroll(driver, steps=3):
    h = driver.execute_script("return document.body.scrollHeight") or 2000
    for i in range(steps):
        y = int(h * (i + 1) / (steps + 1))
        driver.execute_script(f"window.scrollTo({{top:{y}, left:0, behavior:'smooth'}});")
        time.sleep(random.uniform(0.35, 0.8))

def get_attr_safe(el, attr) -> Optional[str]:
    try:
        v = el.get_attribute(attr)
        return v.strip() if v else None
    except Exception:
        return None

def get_text_safe(driver, by, sel) -> Optional[str]:
    try:
        el = driver.find_element(by, sel)
        t = el.text.strip()
        return t if t else None
    except NoSuchElementException:
        return None

def price_to_float(text: Optional[str]) -> Optional[float]:
    if not text: return None
    m = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})|\d+(?:\.\d{1,2})?)", text)
    if not m: return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def slugify(value: str, max_len: int = 64) -> str:
    val = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    val = re.sub(r"_+", "_", val).strip("_")
    return (val[:max_len] or "untitled").strip("_")


# ------------ LISTING PAGE ------------
def collect_all_listing_links(driver, start_url: str) -> List[str]:
    links: List[str] = []
    url = start_url

    while True:
        driver.get(url)
        try:
            wait_css(driver, "#srp-river-results")
        except TimeoutException:
            time.sleep(2)

        js_scroll(driver, 4)

        anchors = driver.find_elements(By.CSS_SELECTOR, "#srp-river-results ul.srp-results li.s-item a.s-item__link")
        if not anchors:
            anchors = driver.find_elements(By.CSS_SELECTOR, "#srp-river-results a[href*='/itm/']")

        seen: Set[str] = set()
        page_links: List[str] = []
        for a in anchors:
            href = get_attr_safe(a, "href")
            if href and "/itm/" in href:
                clean = href.split("?")[0]
                if clean not in seen:
                    seen.add(clean)
                    page_links.append(clean)

        links.extend(page_links)

        next_btn = None
        for sel in ("a.pagination__next", "a[aria-label='Next page']", "nav[role='navigation'] a[rel='next']"):
            cand = driver.find_elements(By.CSS_SELECTOR, sel)
            if cand:
                next_btn = cand[0]
                break

        if next_btn and next_btn.is_enabled():
            next_href = get_attr_safe(next_btn, "href")
            if not next_href or next_href == url:
                break
            url = next_href
            time.sleep(random.uniform(0.7, 1.4))
        else:
            break

    return links


# ------------ PRODUCT IMAGES ------------
def collect_image_urls_from_picturepanel(driver) -> List[str]:
    urls: Set[str] = set()
    try:
        thumb_container = driver.find_element(By.XPATH, "//*[@id='PicturePanel']/div[1]/div/div[1]/div[1]/div[2]")
        thumbs = thumb_container.find_elements(By.XPATH, ".//div/button/img")
        for img in thumbs:
            src = get_attr_safe(img, "src") or get_attr_safe(img, "data-src") or get_attr_safe(img, "data-zoom-src")
            if src:
                urls.add(src)
    except NoSuchElementException:
        pass

    try:
        for img in driver.find_elements(By.CSS_SELECTOR, "#PicturePanel img"):
            src = get_attr_safe(img, "src") or get_attr_safe(img, "data-src") or get_attr_safe(img, "data-zoom-src")
            if src:
                urls.add(src)
    except Exception:
        pass

    if not urls:
        for img in driver.find_elements(By.CSS_SELECTOR, "div.ux-image-grid img, .magnify img"):
            src = get_attr_safe(img, "src") or get_attr_safe(img, "data-src") or get_attr_safe(img, "data-zoom-src")
            if src:
                urls.add(src)

    upgraded = set()
    for u in urls:
        upgraded.add(re.sub(r"/s-l\d+\.", "/s-l1600.", u))
    return list(upgraded or urls)

def download_as_webp(img_url: str, dest_path: str) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(img_url, headers=headers, timeout=20)
        if r.status_code != 200:
            return False
        img_bytes = io.BytesIO(r.content)
        with Image.open(img_bytes) as im:
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGBA")
            else:
                im = im.convert("RGB")
            im.save(dest_path, format="WEBP", quality=90, method=6)
        return True
    except Exception:
        return False

# ------------ PRODUCT FIELDS ------------
def extract_specs(driver) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    try:
        tab = driver.find_elements(By.CSS_SELECTOR, "#viTabs_0_is")
        if tab:
            dls = tab[0].find_elements(By.TAG_NAME, "dl")
            for dl in dls:
                try:
                    dts = dl.find_elements(By.TAG_NAME, "dt")
                    dds = dl.find_elements(By.TAG_NAME, "dd")
                    for dt, dd in zip(dts, dds):
                        k = dt.text.strip()
                        v = dd.text.strip()
                        if k:
                            specs[k] = v
                except Exception:
                    continue
    except Exception:
        pass

    try:
        blocks = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='ux-layout-section-evo__item'] dl.ux-labels-values")
        for block in blocks:
            try:
                label = block.find_element(By.CSS_SELECTOR, "dt").text.strip()
                value = block.find_element(By.CSS_SELECTOR, "dd").text.strip()
                if label:
                    specs[label] = value
            except NoSuchElementException:
                continue
    except Exception:
        pass

    return specs

def choose_images_folder(item_number: Optional[str], name: Optional[str], product_idx: int) -> str:
    """
    Prefer item_number; else slug of name; else product_<index>.
    Ensure non-empty and filesystem-safe.
    """
    if item_number:
        folder = slugify(item_number, 80)
        if folder:
            return folder
    if name:
        folder = slugify(name, 80)
        if folder:
            return folder
    return f"product_{product_idx}"

def scrape_product_data(driver, url: str, product_idx: int) -> Dict:
    driver.get(url)
    try:
        WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1, #PicturePanel")))
    except TimeoutException:
        time.sleep(3)

    js_scroll(driver, 3)

    name = (
        get_text_safe(driver, By.CSS_SELECTOR, "#mainContent h1")
        or get_text_safe(driver, By.CSS_SELECTOR, "h1[itemprop='name']")
        or get_text_safe(driver, By.XPATH, "//*[@id='mainContent']/div[1]/div[1]/h1")
        or get_text_safe(driver, By.XPATH, "//*[@id='mainContent']/div[1]/div[1]/h1/span")
    )

    price_text = (
        get_text_safe(driver, By.XPATH, "//*[@id='mainContent']/div[1]/div[3]/div[1]/div/div[1]/span")
        or get_text_safe(driver, By.CSS_SELECTOR, "#mainContent .x-price-primary span")
        or get_text_safe(driver, By.CSS_SELECTOR, "span[itemprop='price']")
        or get_text_safe(driver, By.CSS_SELECTOR, "#prcIsum, span#prcIsum")
    )
    price = price_to_float(price_text)

    condition = (
        get_text_safe(driver, By.XPATH, "//*[@id='mainContent']/div[1]/div[4]/div[2]/div/span/span[1]/span")
        or get_text_safe(driver, By.CSS_SELECTOR, "#mainContent .x-item-condition-text span span:nth-child(1) span")
        or get_text_safe(driver, By.CSS_SELECTOR, "#vi-itm-cond")
        or get_text_safe(driver, By.CSS_SELECTOR, "div.x-item-condition-text")
    )

    item_number = (
        get_text_safe(driver, By.XPATH, "//span[contains(., 'Item number')]/following::span[1]")
        or get_text_safe(driver, By.CSS_SELECTOR, ".ux-layout-section--itemId .ux-textspans--BOLD")
    )

    # decide images folder name based on a column value (item_number > name > product_index)
    images_folder = choose_images_folder(item_number, name, product_idx)

    # ensure unique folder if a duplicate exists (rare)
    final_folder = images_folder
    attempt = 1
    while os.path.exists(os.path.join(BASE_IMG_DIR, final_folder)) and attempt < 5:
        final_folder = f"{images_folder}_{attempt}"
        attempt += 1

    product_folder = os.path.join(BASE_IMG_DIR, final_folder)
    ensure_dir(product_folder)

    img_urls = collect_image_urls_from_picturepanel(driver)
    img_filenames: List[str] = []
    img_rel_paths: List[str] = []

    for i, u in enumerate(img_urls, start=1):
        fname = f"img{i}.webp"
        dest = os.path.join(product_folder, fname)
        if download_as_webp(u, dest):
            img_filenames.append(fname)
            img_rel_paths.append(os.path.join(BASE_IMG_DIR, final_folder, fname).replace("\\", "/"))
        time.sleep(random.uniform(0.1, 0.25))

    specs = extract_specs(driver)

    return {
        "product_index": product_idx,
        "url": url,
        "name": name,
        "price": price,
        "condition": condition,
        "specs": specs,
        "item_number": item_number,
        "images_folder": final_folder,          # <-- folder used on disk
        "images": img_filenames,                # filenames only
        "image_paths": img_rel_paths,           # relative paths for convenience
    }

# ------------ MAIN ------------
def main():
    ensure_dir(BASE_IMG_DIR)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_xlsx = f"ebay_full_{ts}.xlsx"

    driver = create_driver(headless=HEADLESS)
    rows: List[Dict] = []

    try:
        print("Collecting product links…")
        links = collect_all_listing_links(driver, START_URL)
        print(f"Found {len(links)} product links.")

        for idx, link in enumerate(links, start=1):
            print(f"({idx}/{len(links)}) {link}")
            rec = None
            try:
                rec = scrape_product_data(driver, link, idx)
            except (TimeoutException, WebDriverException) as e:
                print(f"  Retry after error: {e}")
                time.sleep(1.5)
                try:
                    rec = scrape_product_data(driver, link, idx)
                except Exception as e2:
                    print(f"  FAILED: {e2}")

            if rec:
                row = rec.copy()
                row["images"] = json.dumps(row.get("images", []), ensure_ascii=False)
                row["image_paths"] = json.dumps(row.get("image_paths", []), ensure_ascii=False)
                row["specs"] = json.dumps(row.get("specs", {}), ensure_ascii=False)
                rows.append(row)

                if idx % CHECKPOINT_EVERY == 0:
                    pd.DataFrame(rows).to_excel(out_xlsx, index=False)
                    print(f"  checkpoint saved → {out_xlsx}")

            time.sleep(random.uniform(0.6, 1.4))

        pd.DataFrame(rows).to_excel(out_xlsx, index=False)
        print(f"\nDONE. Saved {len(rows)} rows → {out_xlsx}")
        print(f"Images stored under: {os.path.abspath(BASE_IMG_DIR)}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    main()