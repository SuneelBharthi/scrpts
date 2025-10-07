import time
import random
import logging
import re
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from colorama import Fore, init
import unittest
from fake_useragent import UserAgent
import tempfile
import shutil
import os
import atexit
import signal
import warnings
from selenium.webdriver.chrome.service import Service

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)

init(autoreset=True)
class UPCItemDBScraper(unittest.TestCase):

    EXCEL_FILE = "4th-50k.xlsx"                    # input SKUs (expects a 'SKU' column)
    XLSX_FILE  = "EAN-13_results-4th-50k.xlsx"      # output XLSX only
    NOT_FOUND_FILE = "upcitemdb_not_found_skus-4th-50k.txt"
    BASE_URL = "https://www.upcitemdb.com/upc/{}"  # append SKU

    @classmethod
    def setUpClass(cls):
        # Hardcoded Chrome binary + fallback detection
        chrome_binary = r"C:\tools\chrome-win64\chrome.exe"
        if not os.path.exists(chrome_binary):
            for path in (
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ):
                if os.path.exists(path):
                    chrome_binary = path
                    break

        chrome_driver = r"C:\tools\chromedriver-win64\chromedriver.exe"
        options = uc.ChromeOptions()
        ua = UserAgent()
        user_agent = ua.random
        options.add_argument(f"user-agent={user_agent}")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.binary_location = chrome_binary
        cls.temp_profile_dir = tempfile.mkdtemp(prefix="chrome_profile_")
        options.add_argument(f"--user-data-dir={cls.temp_profile_dir}")
        width = random.randint(1200, 1920)
        height = random.randint(800, 1080)
        options.add_argument(f"--window-size={width},{height}")

        service = Service(chrome_driver)

        cls.driver = uc.Chrome(
            options=options,
            service=service,
            version_main=140,   # align with installed Chrome
            headless=True,      # UC headless flag
            browser_executable_path=chrome_binary,
        )
        # Anti-bot evasions
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

        def cleanup_profiles(*args):
            if hasattr(cls, "temp_profile_dir") and os.path.exists(cls.temp_profile_dir):
                shutil.rmtree(cls.temp_profile_dir, ignore_errors=True)
            print(Fore.MAGENTA + f"🧹 Cleaned up profile: {cls.temp_profile_dir}")
        atexit.register(cleanup_profiles)
        signal.signal(signal.SIGTERM, cleanup_profiles)
        signal.signal(signal.SIGINT, cleanup_profiles)
        print(
            Fore.CYAN
            + f"🚀 UPCItemDB Scraper Ready (HEADLESS) | UA: {user_agent} | {width}x{height} | Profile: {cls.temp_profile_dir}"
        )
    @staticmethod
    def setup_logger():
        logger = logging.getLogger("upcitemdb_scraper")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            fh = logging.FileHandler("upcitemdb_scraper.log", encoding="utf-8")
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        return logger

    @classmethod
    def load_previous_results(cls):
        data, processed = [], set()
        not_found = set()
        # Resume from XLSX if exists
        if os.path.exists(cls.XLSX_FILE):
            try:
                df = pd.read_excel(cls.XLSX_FILE)
                if not df.empty:
                    data = df.to_dict("records")
                    if "SKU" in df.columns:
                        processed = set(df["SKU"].astype(str).unique())
                    print(Fore.GREEN + f"🔄 Resuming with {len(processed)} SKUs already processed (from XLSX).")
            except Exception as e:
                print(Fore.YELLOW + f"Warning reading existing XLSX: {e}")

        # Already marked not found
        if os.path.exists(cls.NOT_FOUND_FILE):
            with open(cls.NOT_FOUND_FILE, "r") as f:
                not_found = set(line.strip() for line in f if line.strip())
            print(Fore.RED + f"🔄 Skipping {len(not_found)} SKUs already marked as not found.")
        return data, processed.union(not_found)

    def append_and_save(self, new_data):
        """Save results in real-time to XLSX only."""
        if not new_data:
            return
        self.master_data.extend(new_data)
        df = pd.DataFrame(self.master_data)
        try:
            df.to_excel(self.XLSX_FILE, index=False)
        except Exception as e:
            print(Fore.YELLOW + f"Excel write warning: {e}")
        print(Fore.CYAN + f"💾 Saved {len(new_data)} new records. Total: {len(self.master_data)}")

    def load_skus(self):
        df = pd.read_excel(self.EXCEL_FILE)
        col = "SKU"
        if col not in df.columns:
            raise KeyError(f"Input file '{self.EXCEL_FILE}' must contain a '{col}' column.")
        return [str(x).strip() for x in df[col].dropna().astype(str).unique()]

    def log_not_found(self, sku):
        with open(self.NOT_FOUND_FILE, "a") as f:
            f.write(sku + "\n")
        self.processed_skus.add(sku)
        print(Fore.MAGENTA + f"📭 Logged {sku} as not found.")
    # ---------- Core helpers (EXACT MATCH) ----------
    @staticmethod
    def _normalize_code(s: str) -> str:
        """Lowercase and remove all non-alphanumeric to compare codes robustly."""
        return "".join(ch.lower() for ch in s if ch.isalnum())

    @staticmethod
    def _sku_tokens_from_text(text: str):
        """
        Extract SKU-like tokens from a line of text.
        Tokens include alphanumerics and -, _, /, . characters, starting with alnum.
        Example: 'HP 225 Wired ... 286J4AAABA' -> ['HP', '225', 'Wired', ..., '286J4AAABA']
        """
        return re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_/\.]*", text)

    def _open_search(self, sku):
        url = self.BASE_URL.format(sku)
        self.driver.get(url)
        return url

    def _click_exact_match_in_list(self, sku):
        """
        EXACT match:
        - For each result li, take ./div/p text.
        - Tokenize into SKU-like tokens.
        - Normalize each token and compare equality to normalized searched SKU.
        - Only click when there is an equal token (no prefix/suffix false positives).
          e.g., 286J4AA != 286J4AAABA  (no click)
                28685b == 28685b      (click)
                400-AHYT == 400-Ahyt  (click)
        """
        try:
            ul = WebDriverWait(self.driver, 7).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div/div/div/div[1]/ul"))
            )
        except TimeoutException:
            return False  # Possibly already on detail page
        sku_norm = self._normalize_code(sku)
        items = ul.find_elements(By.XPATH, "./li")
        for idx, li in enumerate(items, start=1):
            try:
                p = li.find_element(By.XPATH, "./div/p")
                p_text = p.text.strip()
                tokens = self._sku_tokens_from_text(p_text)

                # Check equality against each normalized token
                matched = False
                for t in tokens:
                    if self._normalize_code(t) == sku_norm:
                        matched = True
                        break

                if matched:
                    # Scroll & click (prefer anchor if present)
                    try:
                        a = li.find_element(By.TAG_NAME, "a")
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", a)
                        a.click()
                    except NoSuchElementException:
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", li)
                        li.click()
                    print(Fore.GREEN + f"✔️ EXACT token match for '{sku}' at li[{idx}] → clicked")
                    return True
                else:
                    print(Fore.YELLOW + f"… no exact token match for '{sku}' in li[{idx}]")
            except NoSuchElementException:
                continue
        return False

    def _extract_ean_from_detail(self):
        """
        Find the row in //*[@id='info']/table/tbody whose first td label mentions 'EAN' and '13'.
        Return exactly 13 digits from the second td. Ignore all other rows (e.g., UPC-A).
        """
        try:
            info_tbody = WebDriverWait(self.driver, 7).until(
                EC.presence_of_element_located((By.XPATH, "//*[@id='info']/table/tbody"))
            )
            rows = info_tbody.find_elements(By.XPATH, "./tr")
            for row in rows:
                try:
                    label = row.find_element(By.XPATH, "./td[1]").text.strip().lower()
                    if "ean" in label and "13" in label:
                        value_text = row.find_element(By.XPATH, "./td[2]").text.strip()
                        m = re.search(r"\b(\d{13})\b", value_text.replace(" ", ""))
                        if m:
                            return m.group(1)
                        digits = "".join(ch for ch in value_text if ch.isdigit())
                        if len(digits) >= 13:
                            return digits[:13]
                        return None
                except NoSuchElementException:
                    continue
            return None
        except (TimeoutException, NoSuchElementException):
            return None
    # ---------- main flow ----------
    def search_upcitemdb(self, sku):
        if sku in self.processed_skus:
            print(Fore.YELLOW + f"🔹 SKU {sku} already processed or not found. Skipping.")
            return []
        url_visited = self._open_search(sku)
        clicked = self._click_exact_match_in_list(sku)
        if clicked:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//*[@id='info']"))
            )

        detail_url = self.driver.current_url
        ean13 = self._extract_ean_from_detail()
        results = []
        if ean13:
            results.append(
                {
                    "SKU": sku,
                    "EAN-13": ean13,
                    "Vendor": "UPCItemDB",
                    "Product URL": detail_url,
                }
            )
            print(Fore.GREEN + f"✅ EAN-13 found for {sku}: {ean13}")
            self.append_and_save(results)
            self.processed_skus.add(sku)
        else:
            print(Fore.RED + f"❌ EAN-13 not found for {sku}")
            self.log_not_found(sku)

        return results
    # ---------- Test Runner ----------
    def test_scrape_upcitemdb(self):
        skus = self.load_skus()
        for sku in skus:
            print(Fore.YELLOW + f"🔎 Searching SKU: {sku}")
            try:
                self.search_upcitemdb(sku)
            except Exception as e:
                print(Fore.RED + f"Error while processing {sku}: {e}")

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls, "driver") and cls.driver:
                cls.driver.quit()
        except Exception as e:
            print(Fore.RED + f"Error while quitting the driver: {e}")
        if hasattr(cls, "temp_profile_dir") and os.path.exists(cls.temp_profile_dir):
            shutil.rmtree(cls.temp_profile_dir, ignore_errors=True)
        print(Fore.CYAN + "✅ UPCItemDB Scraper Finished, Browser Closed, and Profile Cleaned.")
if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)