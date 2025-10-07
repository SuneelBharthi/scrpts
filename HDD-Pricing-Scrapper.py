import time
import json
import random
import logging
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (TimeoutException,NoSuchElementException,StaleElementReferenceException,WebDriverException,)
from selenium.webdriver import ActionChains
from fake_useragent import UserAgent
from colorama import Fore, init
import tempfile
import warnings
import unittest
import shutil
import atexit
import signal
import os

NET_MAX_RETRIES   = 3      # attempts for network-ish steps
NET_RETRY_DELAY_S = 50    # seconds to wait if net hiccups
PAGELOAD_TIMEOUT  = 50     # navigation timeout
QUICK_PROBE_S = 5          # quick check window for "any results?"
SHORT_WAIT_RESULTS_S = 15   # short fallback wait if probe is uncertain

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)
init(autoreset=True)

class VendorScraper(unittest.TestCase):

    EXCEL_FILE = "4th-50k.xlsx"
    JSON_FILE = "master_scraped_output_4th_50k.json"
    CSV_FILE = "master_scraped_output_4th_50k.csv"
    NOT_FOUND_FILE = "not_found_skus_4th_50k.txt"
    SCRAPED_FILE = "scraped_4th_50k.txt"
    NOT_SCRAPED_FILE = "not-scraped_sec_4th.txt"
    @classmethod
    def setUpClass(cls):
        options = uc.ChromeOptions()
        ua = UserAgent()
        user_agent = ua.random
        options.add_argument(f"user-agent={user_agent}")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        cls.temp_profile_dir = tempfile.mkdtemp(prefix="chrome_profile_")
        options.add_argument(f"--user-data-dir={cls.temp_profile_dir}")
        width = random.randint(1200, 1920)
        height = random.randint(800, 1080)
        options.add_argument(f"--window-size={width},{height}")
        cls.driver = uc.Chrome(options=options, use_subprocess=True)
        cls.driver.set_page_load_timeout(PAGELOAD_TIMEOUT)
        try:
            cls.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
                    window.chrome = { runtime: {} };
                """},
            )
        except Exception:
            pass

        cls.logger = cls.setup_logger()
        cls.master_data, cls.processed_skus = cls.load_previous_results()
        cls.scraped_skus, cls.not_scraped_skus = cls.load_resume_files()
        cls.processed_skus |= cls.scraped_skus | cls.not_scraped_skus
        def cleanup_profiles(*args):
            try:
                if hasattr(cls, "temp_profile_dir") and os.path.exists(cls.temp_profile_dir):
                    shutil.rmtree(cls.temp_profile_dir, ignore_errors=True)
                cls.logger.info(f"Cleaned up profile: {cls.temp_profile_dir}")
            except Exception:
                pass
        atexit.register(cleanup_profiles)
        signal.signal(signal.SIGTERM, cleanup_profiles)
        signal.signal(signal.SIGINT, cleanup_profiles)
        print(Fore.CYAN + f"🚀 Ready | UA: {user_agent} | {width}x{height} | Profile: {cls.temp_profile_dir}")

    @staticmethod
    def setup_logger():
        logger = logging.getLogger("vendor_scraper")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            fh = logging.FileHandler("vendor_scraper.log", encoding="utf-8")
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        return logger
    @classmethod
    def load_previous_results(cls):
        data, processed = [], set()
        if os.path.exists(cls.CSV_FILE):
            df = pd.read_csv(cls.CSV_FILE)
            if not df.empty:
                data = df.to_dict("records")
                if "SKU" in df.columns:
                    processed = set(map(str, df["SKU"].dropna().unique()))
                logging.getLogger("vendor_scraper").info(
                    f"Resuming with {len(processed)} SKUs already processed (from CSV)."
                )
        return data, processed
    @classmethod
    def load_resume_files(cls):
        scraped, not_scraped = set(), set()
        try:
            if os.path.exists(cls.SCRAPED_FILE):
                with open(cls.SCRAPED_FILE, "r", encoding="utf-8") as f:
                    scraped = set(line.strip() for line in f if line.strip())
        except Exception:
            pass
        try:
            if os.path.exists(cls.NOT_SCRAPED_FILE):
                with open(cls.NOT_SCRAPED_FILE, "r", encoding="utf-8") as f:
                    not_scraped = set(line.strip().split(" | ", 1)[0] for line in f if line.strip())
        except Exception:
            pass
        if scraped:
            print(Fore.GREEN + f"🧭 Resume: {len(scraped)} scraped SKUs loaded.")
        if not_scraped:
            print(Fore.YELLOW + f"🧭 Resume: {len(not_scraped)} not-scraped SKUs loaded.")
        return scraped, not_scraped

    def append_and_save(self, new_data):
        if not new_data:
            return
        self.master_data.extend(new_data)
        pd.DataFrame(self.master_data).to_csv(self.CSV_FILE, index=False)
        with open(self.JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(self.master_data, f, indent=4, ensure_ascii=False)
        print(Fore.CYAN + f"💾 Saved {len(new_data)} new records. Total: {len(self.master_data)}")

    def load_skus(self):
        df = pd.read_excel(self.EXCEL_FILE)
        return df["SKU"].dropna().astype(str).unique()
    def log_not_found(self, sku):
        with open(self.NOT_FOUND_FILE, "a", encoding="utf-8") as f:
            f.write(str(sku) + "\n")
    def mark_scraped(self, sku):
        sku = str(sku).strip()
        if sku in getattr(self, "scraped_skus", set()):
            return
        with open(self.SCRAPED_FILE, "a", encoding="utf-8") as f:
            f.write(sku + "\n")
        self.scraped_skus.add(sku)

    def mark_not_scraped(self, sku, reason=""):
        sku = str(sku).strip()
        if sku in getattr(self, "not_scraped_skus", set()):
            return
        with open(self.NOT_SCRAPED_FILE, "a", encoding="utf-8") as f:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{sku} | {reason} | {stamp}\n")
        self.not_scraped_skus.add(sku)

    # ====== XPATHS ======
    LIST_CONTAINER_XP = "/html/body/app-root/div/app-listing/div[2]/div[2]/app-product-list/div/div[3]"
    TITLE_ANCHORS_XP  = LIST_CONTAINER_XP + "/div/div/h2/a"
    LISTING_CUR_PRICE_XP_TPL  = LIST_CONTAINER_XP + "/div[{i}]/div/div[2]/div/p[1]"
    LISTING_LIST_PRICE_XP_TPL = LIST_CONTAINER_XP + "/div[{i}]/div/div[2]/div/p[2]"
    PDP_VERIFY_P_XP       = "/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[2]/div[3]/p"
    PDP_CONDITION_TEXT_XP = "//*[@id='p-accordion']/div/div[1]/div[4]/span[2]"
    MISSING_VALUE = "N\\A"
    # ---------- helpers ----------
    @staticmethod
    def _clean(txt: str) -> str:
        return " ".join((txt or "").split())

    @staticmethod
    def _norm(s: str) -> str:
        s = s or ""
        return "".join(ch for ch in s if ch.isalnum()).upper()
    @staticmethod
    def _left_of_dash(text: str) -> str:
        text = text or ""
        return text.split(" - ", 1)[0].strip()

    def _net_retry(self, op_name, func, *args, **kwargs):
        """Run a selenium op with 120s backoff on Timeout/WebDriver errors."""
        last = None
        for attempt in range(1, NET_MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except (TimeoutException, WebDriverException) as e:
                last = e
                if attempt < NET_MAX_RETRIES:
                    print(Fore.YELLOW + f"[net] {op_name} failed ({attempt}/{NET_MAX_RETRIES}): {e}")
                    print(Fore.YELLOW + f"      retry in {NET_RETRY_DELAY_S}s…")
                    time.sleep(NET_RETRY_DELAY_S)
                else:
                    print(Fore.RED + f"[net] {op_name} final fail: {e}")
                    raise

    def _quick_has_results(self, anchors_xpath, nores_xpaths=None, timeout=QUICK_PROBE_S):
        """Return True (has results quickly), False (explicit no-results), or None (uncertain)."""
        nores_xpaths = nores_xpaths or []
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.driver.find_elements(By.XPATH, anchors_xpath):
                return True
            for xp in nores_xpaths:
                if self.driver.find_elements(By.XPATH, xp):
                    return False
            time.sleep(0.25)
        return None

    # ---------- main per-SKU flow ----------
    def search_serversupply(self, sku):
        sku_str = str(sku).strip()
        if sku_str in self.processed_skus:
            print(Fore.YELLOW + f"⏭️ Skipping (resume): {sku_str}")
            return []

        url = f"https://harddiskdirect.com/search/{sku_str}"
        print(Fore.YELLOW + f"🔎 Searching SKU: {sku_str} → {url}")

        # Navigate (network-safe)
        try:
            self._net_retry("GET search page", self.driver.get, url)
        except Exception:
            self.mark_not_scraped(sku_str, "get_failed")
            return []
        # FAST PATH: bail out quickly if no results
        probe = self._quick_has_results(
            self.TITLE_ANCHORS_XP,
            nores_xpaths=[

            ],
            timeout=QUICK_PROBE_S
        )
        if probe is False:
            print(Fore.RED + f"❌ No results for {sku_str} (quick check)")
            self.log_not_found(sku_str)
            self.mark_not_scraped(sku_str, "no_results_quick")
            return []

        if probe is None:
            # Uncertain → short wait only (avoid long hangs)
            try:
                WebDriverWait(self.driver, SHORT_WAIT_RESULTS_S).until(
                    EC.presence_of_element_located((By.XPATH, self.LIST_CONTAINER_XP))
                )
            except TimeoutException:
                print(Fore.RED + f"❌ Results container timed out (short wait) for {sku_str}")
                self.log_not_found(sku_str)
                self.mark_not_scraped(sku_str, "results_container_short_timeout")
                return []

        # Now proceed as usual
        anchors = self.driver.find_elements(By.XPATH, self.TITLE_ANCHORS_XP)
        if not anchors:
            print(Fore.RED + f"❌ No results/anchors for SKU: {sku_str}")
            self.log_not_found(sku_str)
            self.mark_not_scraped(sku_str, "no_anchors")
            return []
        search_norm = self._norm(sku_str)
        chosen = None
        chosen_index = -1
        chosen_title = ""

        for idx, a in enumerate(anchors, start=1):
            try:
                t = (a.text or a.get_attribute("textContent") or "").strip()
                if self._norm(self._left_of_dash(t)) == search_norm:
                    chosen, chosen_index, chosen_title = a, idx, t
                    break
            except StaleElementReferenceException:
                continue

        if not chosen:
            first_txt = (anchors[0].text or anchors[0].get_attribute("textContent") or "").strip()
            print(Fore.RED + f"❌ No EXACT left-of-dash match. First='{first_txt}', searched='{sku_str}'")
            self.log_not_found(sku_str)
            self.mark_not_scraped(sku_str, "no_exact_match_left_of_dash")
            return []
        # Listing prices
        try:
            cp_el = self.driver.find_element(By.XPATH, self.LISTING_CUR_PRICE_XP_TPL.format(i=chosen_index))
            current_price = self._clean(cp_el.text or cp_el.get_attribute("textContent")) or self.MISSING_VALUE
        except Exception:
            current_price = self.MISSING_VALUE
        try:
            lp_el = self.driver.find_element(By.XPATH, self.LISTING_LIST_PRICE_XP_TPL.format(i=chosen_index))
            list_price = self._clean(lp_el.text or lp_el.get_attribute("textContent")) or self.MISSING_VALUE
        except Exception:
            list_price = self.MISSING_VALUE
        # Click to PDP
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", chosen)
            time.sleep(1)
            try:
                chosen.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", chosen)
        except Exception as e:
            print(Fore.RED + f"❌ Click failed for SKU: {sku_str} | title='{chosen_title}' | {e}")
            self.log_not_found(sku_str)
            self.mark_not_scraped(sku_str, "click_failed")
            return []

        if len(self.driver.window_handles) > 1:
            try:
                self.driver.switch_to.window(self.driver.window_handles[-1])
            except Exception:
                pass
        # Wait/verify PDP text (network-safe)
        try:
            self._net_retry(
                "Wait PDP verify text",
                WebDriverWait(self.driver, 15).until,
                EC.presence_of_element_located((By.XPATH, self.PDP_VERIFY_P_XP))
            )
            verify_el = self.driver.find_element(By.XPATH, self.PDP_VERIFY_P_XP)
            verify_text = self._clean(verify_el.text or verify_el.get_attribute("textContent"))
        except Exception:
            print(Fore.RED + f"❌ PDP verify wait failed for {sku_str}")
            self.mark_not_scraped(sku_str, "pdp_verify_wait_failed")
            return []

        if self._norm(verify_text).find(self._norm(sku_str)) == -1:
            print(Fore.RED + f"❌ PDP verify mismatch for {sku_str} | verify='{verify_text}'")
            self.mark_not_scraped(sku_str, "pdp_verify_mismatch")
            return []

        # Condition
        try:
            cond_el = self.driver.find_element(By.XPATH, self.PDP_CONDITION_TEXT_XP)
            condition = self._clean(cond_el.text or cond_el.get_attribute("textContent")) or self.MISSING_VALUE
        except Exception:
            condition = self.MISSING_VALUE

        row = {
            "SKU": sku_str,
            "Product_Link": self.driver.current_url,
            "Current_Price": current_price,
            "List_Price": list_price,
            "Condition": condition,
        }
        self.append_and_save([row])
        self.mark_scraped(sku_str)
        self.processed_skus.add(sku_str)
        if sku_str in self.not_scraped_skus:
            self.not_scraped_skus.discard(sku_str)
        print(Fore.GREEN + f"✔️ {sku_str} | Curr: {current_price} | List: {list_price} | Cond: {condition}")
        return [row]
    def test_scrape_all(self):
        skus = list(self.load_skus())
        todo = [str(s).strip() for s in skus if str(s).strip() not in self.processed_skus]
        if not todo:
            print(Fore.CYAN + "✅ Nothing to do; all SKUs already processed.")
            return
        print(Fore.CYAN + f"📦 To process: {len(todo)} SKUs")
        ok = 0
        fail = 0
        for sku_str in todo:
            rows = self.search_serversupply(sku_str)
            if rows:
                ok += 1
            else:
                fail += 1
        print(Fore.CYAN + f"🏁 Done. OK: {ok} | Failed: {fail}")

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls, 'driver') and cls.driver:
                cls.driver.quit()
        except Exception as e:
            print(Fore.RED + f"Error while quitting the driver: {e}")
        try:
            if hasattr(cls, "temp_profile_dir") and os.path.exists(cls.temp_profile_dir):
                shutil.rmtree(cls.temp_profile_dir, ignore_errors=True)
            print(Fore.CYAN + "✅ Scraper Finished, Browser Closed, and Profile Cleaned.")
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False, verbosity=0)