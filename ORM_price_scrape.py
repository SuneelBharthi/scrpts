import time
import json
import random
import logging
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
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

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)

init(autoreset=True)

class VendorScraper(unittest.TestCase):

    EXCEL_FILE = "hdd_data_sku.xlsx"
    JSON_FILE = "master_scraped_output.json"
    CSV_FILE = "master_scraped_output.csv"
    NOT_FOUND_FILE = "not_found_skus.txt"

    # NEW: resume filepaths
    SCRAPED_FILE = "scraped.txt"
    NOT_SCRAPED_FILE = "not-scraped.txt"

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

        # Temp user profile per run (cleaned up on exit)
        cls.temp_profile_dir = tempfile.mkdtemp(prefix="chrome_profile_")
        options.add_argument(f"--user-data-dir={cls.temp_profile_dir}")

        # Randomised window size
        width = random.randint(1200, 1920)
        height = random.randint(800, 1080)
        options.add_argument(f"--window-size={width},{height}")

        cls.driver = uc.Chrome(options=options, use_subprocess=True)
        cls.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
                window.chrome = { runtime: {} };
                """
            },
        )

        cls.logger = cls.setup_logger()
        cls.master_data, cls.processed_skus = cls.load_previous_results()

        # NEW: load resume state (scraped & not-scraped)
        cls.scraped_skus, cls.not_scraped_skus = cls.load_resume_files()
        # Skip anything already scraped or marked not-scraped
        cls.processed_skus |= cls.scraped_skus | cls.not_scraped_skus

        def cleanup_profiles(*args):
            if hasattr(cls, "temp_profile_dir") and os.path.exists(cls.temp_profile_dir):
                shutil.rmtree(cls.temp_profile_dir, ignore_errors=True)
            print(Fore.MAGENTA + f"🧹 Cleaned up profile: {cls.temp_profile_dir}")
        atexit.register(cleanup_profiles)
        signal.signal(signal.SIGTERM, cleanup_profiles)
        signal.signal(signal.SIGINT, cleanup_profiles)

        print(
            Fore.CYAN
            + f"🚀 Stealth Scraper Ready | UA: {user_agent} | Viewport: {width}x{height} | Profile: {cls.temp_profile_dir}"
        )

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
                print(Fore.GREEN + f"🔄 Resuming with {len(processed)} SKUs already processed (from CSV).")
        return data, processed

    @classmethod
    def load_resume_files(cls):
        """Load scraped.txt and not-scraped.txt as sets of SKUs (strings)."""
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

    # NEW: mark resume status
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
            # Keep a simple reason trail for debugging
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            line = f"{sku} | {reason} | {stamp}\n"
            f.write(line)
        self.not_scraped_skus.add(sku)

    # ====== SEARCH LISTING CONTAINER ======
    LIST_CONTAINER_XP = "/html/body/app-root/div/app-listing/div[2]/div[2]/app-product-list/div/div[3]"
    CARD_LIST_XP      = LIST_CONTAINER_XP + "/div"                 # all product card <div>s
    TITLE_ANCHORS_XP  = LIST_CONTAINER_XP + "/div/div/h2/a"        # title anchors in each card
    # ====== PDP XPATHS ======
    PDP_PRICE_BLOCK_XP  = "/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[3]/div/div[2]"
    PDP_CUR_PRICE_XP    = PDP_PRICE_BLOCK_XP + "/div/p[1]"  # current price
    PDP_LIST_PRICE_XP   = PDP_PRICE_BLOCK_XP + "/div/p[2]"  # list price
    PDP_CONDITION_DIV_XP  = "//*[@id='p-accordion']/div/div[1]/div[4]"
    PDP_CONDITION_TEXT_XP = "//*[@id='p-accordion']/div/div[1]/div[4]/span[2]"
    MISSING_VALUE = "N\\A"

    @staticmethod
    def _clean(txt: str) -> str:
        return " ".join((txt or "").split())

    @staticmethod
    def _norm(s: str) -> str:
        """Uppercase alphanumerics only; helps fuzzy 'contains' match."""
        s = s or ""
        return "".join(ch for ch in s if ch.isalnum()).upper()

    def search_serversupply(self, sku):
        sku_str = str(sku).strip()
        if sku_str in self.processed_skus:
            print(Fore.YELLOW + f"🔹 SKU {sku_str} already processed (resume). Skipping.")
            return []

        url = f"https://harddiskdirect.com/search/{sku_str}"
        self.driver.get(url)

        try:
            # Wait for the listing container you specified
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, self.LIST_CONTAINER_XP))
            )
            # ===== Step 1: find a title whose text contains the searched SKU (normalized) =====
            anchors = self.driver.find_elements(By.XPATH, self.TITLE_ANCHORS_XP)
            if not anchors:
                print(Fore.RED + f"❌ No results container/anchors found for SKU: {sku_str}")
                self.log_not_found(sku_str)
                self.mark_not_scraped(sku_str, "no_anchors")
                return []
            sku_norm = self._norm(sku_str)
            chosen = None
            chosen_text = ""

            for a in anchors:
                try:
                    a_text = (a.text or a.get_attribute("textContent") or "").strip()
                    a_norm = self._norm(a_text)
                    # Accept if search SKU is a substring of anchor text (or vice versa, to allow shortened input)
                    if sku_norm and (sku_norm in a_norm or a_norm in sku_norm):
                        chosen = a
                        chosen_text = a_text
                        break
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue

            if not chosen:
                # As a debug aid, show first anchor text found
                first_txt = (anchors[0].text or anchors[0].get_attribute("textContent") or "").strip()
                print(Fore.RED + f"❌ No title contains searched SKU. First title was '{first_txt}', searched '{sku_str}'")
                self.log_not_found(sku_str)
                self.mark_not_scraped(sku_str, "no_title_contains_sku")
                return []
            # ===== Step 2: click matched anchor and go to PDP =====
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", chosen)
                time.sleep(0.2)
                try:
                    chosen.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", chosen)
            except Exception:
                print(Fore.RED + f"❌ Could not click matched title for SKU: {sku_str} (title: '{chosen_text}')")
                self.log_not_found(sku_str)
                self.mark_not_scraped(sku_str, "click_failed")
                return []
            # If it opened a new tab, switch to it
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[-1])
            except Exception:
                pass
            # ===== Step 3: wait for PDP content =====
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, self.PDP_PRICE_BLOCK_XP))
                )
            except TimeoutException:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, self.PDP_CONDITION_DIV_XP))
                    )
                except Exception:
                    self.mark_not_scraped(sku_str, "pdp_timeout")
                    raise

            # ===== Step 4: scrape prices with N\A fallback =====
            try:
                cur_el = self.driver.find_element(By.XPATH, self.PDP_CUR_PRICE_XP)
                current_price = self._clean(cur_el.text or cur_el.get_attribute("textContent"))
                if not current_price:
                    current_price = self.MISSING_VALUE
            except Exception:
                current_price = self.MISSING_VALUE

            try:
                list_el = self.driver.find_element(By.XPATH, self.PDP_LIST_PRICE_XP)
                list_price = self._clean(list_el.text or list_el.get_attribute("textContent"))
                if not list_price:
                    list_price = self.MISSING_VALUE
            except Exception:
                list_price = self.MISSING_VALUE
            # ===== Step 5: scrape condition =====
            try:
                cond_text_el = self.driver.find_element(By.XPATH, self.PDP_CONDITION_TEXT_XP)
                condition = self._clean(cond_text_el.text or cond_text_el.get_attribute("textContent"))
                if not condition:
                    condition = self.MISSING_VALUE
            except Exception:
                condition = self.MISSING_VALUE
            # ===== Step 6: persist row =====
            product_url = self.driver.current_url
            row = {
                "SKU": sku_str,
                "Product_Link": product_url,
                "Current_Price": current_price,
                "List_Price": list_price,
                "Condition": condition,
            }
            self.append_and_save([row])
            # mark resume state
            self.mark_scraped(sku_str)
            self.processed_skus.add(sku_str)
            # If SKU previously in not-scraped, clean it from memory (file will still keep history)
            if sku_str in self.not_scraped_skus:
                self.not_scraped_skus.discard(sku_str)

            print(Fore.GREEN + f"✔️ {sku_str} → {product_url} | Curr: {current_price} | List: {list_price} | Cond: {condition}")
            return [row]

        except TimeoutException:
            print(Fore.RED + f"❌ Timeout while searching for SKU: {sku_str}")
            self.log_not_found(sku_str)
            self.mark_not_scraped(sku_str, "timeout_search")
            return []
        except StaleElementReferenceException:
            print(Fore.RED + f"♻️ Stale DOM while processing SKU: {sku_str} — retrying once")
            try:
                self.driver.refresh()
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, self.LIST_CONTAINER_XP))
                )
                return self.search_serversupply(sku_str)
            except Exception:
                self.log_not_found(sku_str)
                self.mark_not_scraped(sku_str, "stale_retry_failed")
                return []
        except Exception as e:
            print(Fore.RED + f"Error while processing {sku_str}: {e}")
            self.logger.exception(f"Unhandled error for SKU {sku_str}")
            self.log_not_found(sku_str)
            self.mark_not_scraped(sku_str, f"exception:{type(e).__name__}")
            return []

    # --------- TEST ENTRYPOINT (so unittest actually runs your scrape) ---------
    def test_scrape_all(self):
        """Discoverable by unittest; iterates all SKUs and scrapes, with resume support."""
        skus = self.load_skus()
        for sku in skus:
            sku_str = str(sku).strip()
            if sku_str in self.processed_skus:
                print(Fore.YELLOW + f"⏭️ Skipping (resume): {sku_str}")
                continue
            print(Fore.YELLOW + f"🔎 Searching SKU: {sku_str}")
            self.search_serversupply(sku_str)

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls, 'driver') and cls.driver:
                cls.driver.quit()
        except Exception as e:
            print(Fore.RED + f"Error while quitting the driver: {e}")
        if hasattr(cls, "temp_profile_dir") and os.path.exists(cls.temp_profile_dir):
            shutil.rmtree(cls.temp_profile_dir, ignore_errors=True)
        print(Fore.CYAN + "✅ Scraper Finished, Browser Closed, and Profile Cleaned.")

if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)