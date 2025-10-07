import unittest
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service
from fake_useragent import UserAgent
import tempfile
import shutil
import os
import random
import pandas as pd
from colorama import Fore, init
import atexit
import signal
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)

init(autoreset=True)

class NetworkDevicesIncScraper(unittest.TestCase):
    EXCEL_FILE = "tst.xlsx"   # ✅ Excel file containing SKUs

    @classmethod
    def setUpClass(cls):
        chrome_binary = r"C:\tools\chrome-win64\chrome.exe"
        if not os.path.exists(chrome_binary):
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

        cls.driver = uc.Chrome(
            options=options,
            service=service,
            version_main=140,
            headless=False,
            browser_executable_path=chrome_binary
        )

        atexit.register(lambda *args: shutil.rmtree(cls.temp_profile_dir, ignore_errors=True))
        signal.signal(signal.SIGTERM, lambda *args: shutil.rmtree(cls.temp_profile_dir, ignore_errors=True))
        signal.signal(signal.SIGINT, lambda *args: shutil.rmtree(cls.temp_profile_dir, ignore_errors=True))

        print(Fore.CYAN + f"🚀 NetworkDevicesInc Scraper Ready | UA: {user_agent}")

    def load_skus(self):
        df = pd.read_excel(self.EXCEL_FILE)
        return df["SKU"].dropna().unique()
    def test_scrape_networkdevicesinc(self):
        skus = self.load_skus()
        total = len(skus)
        for i, sku in enumerate(skus, start=1):
            url = f"https://networkdevicesinc.com/search/{sku}"
            print(Fore.YELLOW + f"🔎 Searching {i}/{total} | SKU: {sku}")
            try:
                self.driver.get(url)
            except Exception as e:
                print(Fore.RED + f"Error while opening {url}: {e}")

    @classmethod
    def tearDownClass(cls):
        try:
            if hasattr(cls, "driver") and cls.driver:
                cls.driver.quit()
        except Exception as e:
            print(Fore.RED + f"Error closing driver: {e}")

        if hasattr(cls, "temp_profile_dir") and os.path.exists(cls.temp_profile_dir):
            shutil.rmtree(cls.temp_profile_dir, ignore_errors=True)

        print(Fore.CYAN + "✅ Browser Closed and Profile Cleaned.")
if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)