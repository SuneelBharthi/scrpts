import os, re, time, random, platform, subprocess, shutil
import logging
from tqdm import tqdm
from pathlib import Path
from typing import List, Optional, Tuple
import pandas as pd
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

# --------------------- CONFIG ---------------------
INPUT_XLSX = "gtin.xlsx"          # Must contain column 'sku'
OUTPUT_XLSX = "google_gtin_results.xlsx"
LOG_FILE = "scrape_google.log"
SCRAPED_SKUS_FILE = "scraped_skus.txt"
NOT_SCRAPED_SKUS_FILE = "not_scraped_skus.txt"
HEADLESS = True                  # Headful gets fewer CAPTCHAs on Google
PER_QUERY_DELAY = (1.0, 2.0)      # polite jitter between searches
PAGE_LOAD_TIMEOUT = 35
# CAPTCHA handling
MANUAL_CAPTCHA_SOLVE = True       # prompt user to solve when detected
CAPTCHA_WAIT_SECONDS = 80    # wait up to 3 minutes for manual solve
COOLDOWN_ON_CAPTCHA = (20, 30)  # backoff when we can’t clear it

# If no Excel, use these demo SKUs:
fallback_queries = ["AIR-SAP2602I-E-K9", "NIM-4FXS"]

# XPaths you provided (checked in order until text is found)
USER_RESULT_XPATHS = [
    "//*[@id='m-x-content']/div/div",
    "//*[@id='m-x-content']/div/div/div",
    "//*[@id='m-x-content']/div/div/div/div",
    "//*[@id='m-x-content']/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div",
    "//*[@id='m-x-content']/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div",
    "//*[@id='m-x-content']/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div/div",
    "//*[@id='m-x-content']/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div/div/div",
    "//*[@id='m-x-content']/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div/div/div/div[2]/div[1]/section/div/div",
    "//*[@id='m-x-content']/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div/div/div/div[2]/div[1]/section/div/div/div/div[1]/div/div[1]/div[2]",
    "//*[@id='m-x-content']/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div/div/div/div[2]/div[1]/section/div/div/div/div[1]/div/div[1]/div[2]/div",
    "//*[@id='m-x-content']/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div/div/div/div[2]/div[1]/section/div/div/div/div[1]/div/div[1]/div[2]/div/div[1]",
    "//*[@id='m-x-content']/div/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div/div	div/div[2]/div[1]/section/div/div/div/div[1]/div/div[1]/div[2]/div/div[1]/div",
]

# Google fallbacks if the custom paths don’t appear
GOOGLE_FALLBACK_SELECTORS = [
    ("css", "div#search div.g h3"),             # result title
    ("css", "div#search div.g div.VwiC3b"),     # result snippet
    ("css", "#search h3"),                      # generic first title
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
]
# Set up logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def log(msg: str):
    """Log messages to both console and file."""
    logging.info(msg)
    print(msg)

def rdelay(a: float, b: float):
    time.sleep(a + random.random() * (b - a))

def get_chrome_major() -> Optional[int]:
    try:
        if platform.system() == "Windows":
            try:
                import winreg  # type: ignore
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon") as k:
                    ver, _ = winreg.QueryValueEx(k, "version")
                    return int(ver.split(".")[0])
            except Exception:
                pass
            for path in [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Applicat ion\chrome.exe",
            ]:
                if os.path.exists(path):
                    out = subprocess.check_output([path, "--version"], text=True)
                    m = re.search(r"\b(\d+)\.", out)
                    if m: return int(m.group(1))
            chrome = shutil.which("chrome") or shutil.which("chrome.exe")
            if chrome:
                out = subprocess.check_output([chrome, "--version"], text=True)
                m = re.search(r"\b(\d+)\.", out)
                if m: return int(m.group(1))
        elif platform.system() == "Darwin":
            for p in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]:
                if os.path.exists(p):
                    out = subprocess.check_output([p, "--version"], text=True)
                    m = re.search(r"\b(\d+)\.", out)
                    if m: return int(m.group(1))
        else:
            for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
                exe = shutil.which(name)
                if exe:
                    out = subprocess.check_output([exe, "--version"], text=True)
                    m = re.search(r"\b(\d+)\.", out)
                    if m: return int(m.group(1))
    except Exception:
        pass
    return None

def build_driver():
    ua = random.choice(USER_AGENTS)
    w, h = random.randint(1200,1600), random.randint(800,1000)

    opts = uc.ChromeOptions()
    if HEADLESS:
         opts.add_argument("--headless=new")
    opts.add_argument(f"--user-agent={ua}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={w},{h}")

    major = get_chrome_major()
    if major:
        driver = uc.Chrome(options=opts, version_main=major)
    else:
        driver = uc.Chrome(options=opts)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    driver.set_script_timeout(PAGE_LOAD_TIMEOUT)
    return driver

def accept_google_consent(driver):
    try:
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            t = (btn.text or "").strip().lower()
            if any(k in t for k in ["i agree", "accept all", "agree to all", "accept"]):
                btn.click()
                rdelay(0.4, 0.9)
                return
    except Exception:
        pass

# ---------- CAPTCHA detection & handling ----------
def is_google_captcha(driver) -> bool:
    url = (driver.current_url or "").lower()
    if "/sorry/" in url or "sorry/index" in url:
        return True
    html = (driver.page_source or "").lower()
    signals = [
        "unusual traffic from your computer network",
        "i'm not a robot",
        "recaptcha",
        "to continue, please type the characters",
    ]
    return any(s in html for s in signals)

def notify_user(driver):
    try:
        driver.maximize_window()
    except Exception:
        pass
    try:
        import winsound
        winsound.Beep(880, 250); winsound.Beep(988, 250)
    except Exception:
        print("\a", end="")  # terminal bell

def wait_for_captcha_clear(driver, timeout=CAPTCHA_WAIT_SECONDS) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if not is_google_captcha(driver):
            return True
        time.sleep(2)
    return False
# -----------------------------------------------------------

def find_by_user_xpaths(driver) -> Tuple[Optional[str], Optional[str]]:
    for xp in USER_RESULT_XPATHS:
        try:
            el = driver.find_element(By.XPATH, xp)
            txt = (el.text or "").strip()
            if txt:
                return txt, xp
        except Exception:
            continue
    return None, None

def google_fallback_text(driver) -> Tuple[Optional[str], Optional[str]]:
    for kind, sel in GOOGLE_FALLBACK_SELECTORS:
        try:
            if kind == "css":
                els = driver.find_elements(By.CSS_SELECTOR, sel)
            else:
                els = driver.find_elements(By.XPATH, sel)
            if els:
                text = (els[0].text or "").strip()
                if text:
                    return text, sel
        except Exception:
            continue
    return None, None

# -------- GTIN/EAN extraction helpers --------
def _find_numbers(text: str, target_len: int) -> List[str]:
    """Find numbers of a specific length allowing spaces/hyphens between digits."""
    if not text: return []
    raw = re.findall(r'(?:\d[\s-]?){'+str(target_len)+r'}', text)
    cleaned = []
    for r in raw:
        d = re.sub(r'\D', '', r)
        if len(d) == target_len:
            cleaned.append(d)
    # Deduplicate preserving order
    seen = set(); out = []
    for x in cleaned:
        if x not in seen:
            seen.add(x); out.append(x)
    return out

def extract_gtin_and_ean13(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (gtin_12, ean13). We ignore other lengths.
    Priority: numbers on lines mentioning gtin/ean; then anywhere.
    """
    if not text: return None, None
    lines = [ln for ln in text.splitlines() if ln.strip()]

    # 13-digit (EAN-13)
    for ln in lines:
        if any(k in ln.lower() for k in ["ean-13", "ean", "gtin-13"]):
            c13 = _find_numbers(ln, 13)
            if c13: ean13 = c13[0]; break
    else:
        c13 = _find_numbers(text, 13)
        ean13 = c13[0] if c13 else None

    # 12-digit (GTIN/UPC)
    for ln in lines:
        if any(k in ln.lower() for k in ["gtin", "gtin-12"]):
            c12 = _find_numbers(ln, 12)
            if c12: gtin12 = c12[0]; break
    else:
        c12 = _find_numbers(text, 12)
        gtin12 = c12[0] if c12 else None

    return gtin12, ean13
# ----------------------------------------------

def search_google(driver, query: str) -> str:
    driver.get("https://www.google.com/")
    rdelay(0.5, 1.2)
    accept_google_consent(driver)

    # Your custom searchbox chain (fallback to Google's standard box if not present)
    try:
        driver.find_element(By.XPATH, "//*[@id='content']")
        driver.find_element(By.XPATH, "//*[@id='searchboxContainer']")
        driver.find_element(By.XPATH, "//*[@id='searchbox']")
        driver.find_element(By.XPATH, "//*[@id='inputWrapper']")
        box = driver.find_element(By.XPATH, "//*[@id='input']")
    except Exception:
        try:
            box = driver.find_element(By.NAME, "q")
        except NoSuchElementException:
            box = driver.find_element(By.CSS_SELECTOR, "textarea[name='q'], input[name='q']")
            return None

    box.clear()
    for ch in query:
        box.send_keys(ch); rdelay(0.04, 0.10)
    box.send_keys(Keys.ENTER)

    # Wait a bit
    rdelay(2, 4)

    # CAPTCHA check
    if is_google_captcha(driver):
        if MANUAL_CAPTCHA_SOLVE:
            notify_user(driver)
            ok = wait_for_captcha_clear(driver, CAPTCHA_WAIT_SECONDS)
            if not ok:
                rdelay(*COOLDOWN_ON_CAPTCHA)
                return ""  # caller may retry once
        else:
            return ""

    # Try your XPacths first
    txt, _ = find_by_user_xpaths(driver)
    if txt:
        return txt

    # Google fallbacks
    txt, _ = google_fallback_text(driver)
    if txt:
        return txt

    # Soup last resort
    try:
        soup = BeautifulSoup(driver.page_source, "lxml")
        h3 = soup.select_one("#search h3")
        if h3 and h3.get_text(strip=True):
            return h3.get_text(strip=True)
        snip = soup.select_one("#search .VwiC3b")
        if snip and snip.get_text(strip=True):
            return snip.get_text(strip=True)
    except Exception:
        pass
    return ""

# In your main function, wrap the SKU processing loop with tqdm
def main():
    # Load SKUs from Excel if present; else use fallback list
    if Path(INPUT_XLSX).exists():
        df = pd.read_excel(INPUT_XLSX)
        if "sku" in df.columns:
            skus = [str(x).strip() for x in df["sku"].dropna().tolist() if str(x).strip()]
        else:
            skus = fallback_queries
    else:
        skus = fallback_queries

    rows = []
    scraped_skus = set()
    not_scraped_skus = set()
    
    # Load previously scraped SKUs to resume
    if Path(SCRAPED_SKUS_FILE).exists():
        with open(SCRAPED_SKUS_FILE, 'r') as f:
            scraped_skus = set(f.read().splitlines())
    
    if Path(NOT_SCRAPED_SKUS_FILE).exists():
        with open(NOT_SCRAPED_SKUS_FILE, 'r') as f:
            not_scraped_skus = set(f.read().splitlines())

    driver = build_driver()
    try:
        # Use tqdm to track the progress of the SKUs being processed
        for sku in tqdm(skus, desc="Scraping SKUs", unit="SKU"):
            if sku in scraped_skus:
                continue  # Skip already scraped SKUs

            query = f"{sku} gtin / ean-13 number"
            text = search_google(driver, query)

            # If CAPTCHA blocked and returned empty, cool down & retry once
            if not text:
                rdelay(*COOLDOWN_ON_CAPTCHA)
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = build_driver()
                text = search_google(driver, query)

            gtin12, ean13 = extract_gtin_and_ean13(text)
            rows.append({"sku": sku, "gtin": gtin12 or "", "ean-13": ean13 or ""})

            # Log the scraped SKU
            scraped_skus.add(sku)
            with open(SCRAPED_SKUS_FILE, 'a') as f:
                f.write(f"{sku}\n")

            # Log the not scraped SKU if no GTIN/EAN found
            if not gtin12 and not ean13:
                not_scraped_skus.add(sku)
                with open(NOT_SCRAPED_SKUS_FILE, 'a') as f:
                    f.write(f"{sku}\n")
            
            # Save results after each query
            out_df = pd.DataFrame(rows, columns=["sku", "gtin", "ean-13"])
            out_df.to_excel(OUTPUT_XLSX, index=False)

            rdelay(*PER_QUERY_DELAY)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    log(f"Scraped {len(rows)} SKUs and saved to {OUTPUT_XLSX}")
    log(f"Scraped SKUs saved in {SCRAPED_SKUS_FILE}")
    log(f"Not scraped SKUs saved in {NOT_SCRAPED_SKUS_FILE}")

if __name__ == "__main__":
    random.seed()
    main()