import time
import random
import json
import logging
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

class RouterSwitchScraper(unittest.TestCase):
    EXCEL_FILE = "4th-50k.xlsx"
    JSON_FILE = "master-excel-hdd-4-50K.json"
    CSV_FILE = "master-json-hdd_4_50K.csv"
    NOT_FOUND_FILE = "HDD_not_found_skus_4-50K.txt"

    @classmethod
    def setUpClass(cls):
        # Hardcoded Chrome binary + fallback detection
        chrome_binary = r"C:\tools\chrome-win64\chrome.exe"
        if not os.path.exists(chrome_binary):
            # Try common install paths if hardcoded one is missing
            possible_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            ]
            for path in possible_paths:
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

        # ✅ FIX: add browser_executable_path so UC finds Chrome
        cls.driver = uc.Chrome(
            options=options,
            service=service,
            version_main=140,   # Match Chrome version
            headless=False,
            browser_executable_path=chrome_binary
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
            + f"🚀 RouterSwitch Scraper Ready | UA: {user_agent} | Viewport: {width}x{height} | Profile: {cls.temp_profile_dir}"
        )

    @staticmethod
    def setup_logger():
        logger = logging.getLogger("router_switch_scraper")
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            fh = logging.FileHandler("router_switch_scraper.log", encoding="utf-8")
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        return logger

    @classmethod
    def load_previous_results(cls):
        data, processed = [], set()
        not_found = set()

        # Already found results
        if os.path.exists(cls.CSV_FILE):
            df = pd.read_csv(cls.CSV_FILE)
            if not df.empty:
                data = df.to_dict("records")
                processed = set(df["SKU"].unique())
                print(Fore.GREEN + f"🔄 Resuming with {len(processed)} SKUs already processed.")

        # Already marked not found
        if os.path.exists(cls.NOT_FOUND_FILE):
            with open(cls.NOT_FOUND_FILE, "r") as f:
                not_found = set(line.strip() for line in f if line.strip())
            print(Fore.RED + f"🔄 Skipping {len(not_found)} SKUs already marked as not found.")

        return data, processed.union(not_found)

    def append_and_save(self, new_data):
        """Save results in real-time to CSV + JSON"""
        self.master_data.extend(new_data)
        pd.DataFrame(self.master_data).to_csv(self.CSV_FILE, index=False)
        with open(self.JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(self.master_data, f, indent=4, ensure_ascii=False)
        print(Fore.CYAN + f"💾 Saved {len(new_data)} new records. Total: {len(self.master_data)}")

    def load_skus(self):
        df = pd.read_excel(self.EXCEL_FILE)
        return df["SKU"].dropna().unique()

    def log_not_found(self, sku):
        """Save not found SKUs in real-time and skip them on resume"""
        with open(self.NOT_FOUND_FILE, "a") as f:
            f.write(sku + "\n")
        self.processed_skus.add(sku)
        print(Fore.MAGENTA + f"📭 Logged {sku} as not found.")

    def search_router_switch(self, sku):
        if sku in self.processed_skus:
            print(Fore.YELLOW + f"🔹 SKU {sku} already processed or not found. Skipping.")
            return []

        url = f"https://www.router-switch.com/search/{sku}"
        self.driver.get(url)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "ol.products.list.items.product-items.row li.item")
                )
            )

            results = []
            products = self.driver.find_elements(By.CSS_SELECTOR, "ol.products.list.items.product-items.row li.item")
            for li in products:
                try:
                    name_el = li.find_element(By.CSS_SELECTOR, "h2.product.name a")
                    found_sku = name_el.text.strip()
                    if found_sku.lower().strip() == sku.lower().strip():
                        condition = "N/A"
                        try:
                            condition = li.find_element(
                                By.CSS_SELECTOR, "p.product-condition"
                            ).text.replace("Condition:", "").strip()
                        except NoSuchElementException:
                            pass

                        list_price = "N/A"
                        try:
                            list_price = li.find_element(By.CSS_SELECTOR, "div.listprice span.price").text.strip()
                        except:
                            pass

                        current_price = "N/A"
                        try:
                            current_price = li.find_element(By.CSS_SELECTOR, "div.price-box span.price").text.strip()
                        except:
                            pass

                        results.append({
                            "SKU": sku,
                            "Vendor": "RouterSwitch",
                            "Product Condition": condition,
                            "List Price": list_price,
                            "Current Price": current_price,
                            "Product URL": name_el.get_attribute("href"),
                        })
                        print(Fore.GREEN + f"✔️ Captured RouterSwitch product for {sku}")

                except Exception:
                    continue

            if not results:
                print(Fore.RED + f"❌ No RouterSwitch products found for SKU: {sku}")
                self.log_not_found(sku)
            else:
                self.append_and_save(results)
                self.processed_skus.add(sku)

            return results

        except TimeoutException:
            print(Fore.RED + f"❌ Timeout while searching RouterSwitch for SKU: {sku}")
            self.log_not_found(sku)
            return []

    def test_scrape_router_switch(self):
        skus = self.load_skus()
        for sku in skus:
            print(Fore.YELLOW + f"🔎 Searching SKU: {sku}")
            try:
                self.search_router_switch(sku)
            except Exception as e:
                print(Fore.RED + f"Error while processing {sku}: {e}")

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls, 'driver') and cls.driver:
                cls.driver.quit()
        except Exception as e:
            print(Fore.RED + f"Error while quitting the driver: {e}")

        if hasattr(cls, "temp_profile_dir") and os.path.exists(cls.temp_profile_dir):
            shutil.rmtree(cls.temp_profile_dir, ignore_errors=True)

        print(Fore.CYAN + "✅ RouterSwitch Scraper Finished, Browser Closed, and Profile Cleaned.")


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
