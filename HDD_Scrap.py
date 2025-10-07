import os
import time
import random
import pandas as pd
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
 
# === Logging Setup ===
logging.basicConfig(filename='harddiskdirect_errors.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')
 
# === Proxy Credentials ===
USERNAME = "gtzx4au8sp6waiw"
PASSWORD = "zjr0wb84h8l0oqr"
HOST = "rp.scrapegw.com"
PORT = "6060"
 
def generate_proxy():
    session = ''.join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
    return f"http://{USERNAME}-session-{session}:{PASSWORD}@{HOST}:{PORT}"
 
def create_driver(proxy_url):
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
 
    seleniumwire_options = {
        'proxy': {
            'http': proxy_url,
            'https': proxy_url,
            'no_proxy': 'localhost,127.0.0.1'
        }
    }
 
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, seleniumwire_options=seleniumwire_options, options=chrome_options)
    return driver
 
def safe_find(driver, xpath, attr='text', timeout=20):
    try:
        WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.XPATH, xpath)))
        el = driver.find_element(By.XPATH, xpath)
        return el.text.strip() if attr == 'text' else el.get_attribute(attr)
    except (NoSuchElementException, TimeoutException):
        return 'N/A'
 
def is_product_url(url):
    return url.startswith("https://harddiskdirect.com/") and url.endswith(".html") and "/categories/" not in url
 
def scrape_product(driver, url):
    data = {
        'Category': 'N/A', 'Sub_Category': 'N/A', 'Child_Category': 'N/A', 'Grand_Child_Category': 'N/A',
        'Product_Name': 'N/A', 'Product_Description': 'N/A', 'Availability': 'N/A', 'Brand': 'N/A',
        'Part_Number': 'N/A', 'Price': 'N/A', 'Image_Link': 'N/A', 'Source_URL': url
    }
 
    try:
        driver.get(url)
        time.sleep(6)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
 
        WebDriverWait(driver, 25).until(EC.visibility_of_element_located((By.XPATH,
            '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/h1')))
 
        part_number = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[2]/div[3]/p')
 
        breadcrumbs = {
            'Category': '/html/body/app-root/div/app-details/div/div/div/div[1]/app-ng-dynamic-breadcrumb/ul/span[2]',
            'Sub_Category': '/html/body/app-root/div/app-details/div/div/div/div[1]/app-ng-dynamic-breadcrumb/ul/span[3]',
            'Child_Category': '/html/body/app-root/div/app-details/div/div/div/div[1]/app-ng-dynamic-breadcrumb/ul/span[4]',
            'Grand_Child_Category': '/html/body/app-root/div/app-details/div/div/div/div[1]/app-ng-dynamic-breadcrumb/ul/span[5]'
        }
 
        for key, path in breadcrumbs.items():
            val = safe_find(driver, path).rstrip('/').strip()
            if key == 'Grand_Child_Category' and val == part_number:
                continue
            data[key] = val
 
        data['Product_Name'] = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/h1')
        if data['Product_Name'] == 'N/A':
            print(f"⚠️ Product Name not found at {url}")
 
        data['Product_Description'] = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[1]')
        avail_label = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[2]/div[1]/div/div')
        if "Availability" in avail_label:
            data['Availability'] = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[2]/div[1]/div/span')
 
        brand_label = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[2]/div[2]/span')
        if "Brand" in brand_label:
            data['Brand'] = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[2]/div[2]/p')
 
        part_label = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[2]/div[3]/span')
        if "Part Number" in part_label:
            data['Part_Number'] = part_number
 
        data['Price'] = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[2]/div[3]/div/div[2]/div/p')
        data['Image_Link'] = safe_find(driver, '/html/body/app-root/div/app-details/div/div/div/div[1]/div/div[1]/div[2]/div/div[1]/figure/img', attr='src')
 
    except Exception as e:
        print(f"❌ Scrape failed for: {url} | {e}")
        logging.error(f"Scrape failed for: {url} | {e}")
 
    return data
 
def scrape_with_retries(driver, url, retries=3):
    for attempt in range(retries):
        print(f"   Attempt {attempt + 1} of {retries}")
        data = scrape_product(driver, url)
        if data['Product_Name'] != 'N/A':
            return data
        time.sleep(3)  # Wait before retrying
    print(f"❌ Failed after {retries} attempts: {url}")
    return data  # return even failed attempt to avoid skipping
 
# === Run Script ===
input_file = 'product_links.xlsx'
output_file = 'harddiskdirect_scraped_data.xlsx'
progress_file = 'HDDprogress.txt'
 
df_links = pd.read_excel(input_file)
urls = df_links['Links'].tolist()
 
start_index = 0
if os.path.exists(progress_file):
    with open(progress_file, 'r') as f:
        content = f.read().strip()
        if content.isdigit():
            start_index = int(content)
 
columns = ['Category', 'Sub_Category', 'Child_Category', 'Grand_Child_Category',
           'Product_Name', 'Product_Description', 'Availability', 'Brand',
           'Part_Number', 'Price', 'Image_Link', 'Source_URL']
 
df_output = pd.read_excel(output_file) if os.path.exists(output_file) else pd.DataFrame(columns=columns)
 
for i in range(start_index, len(urls)):
    url = urls[i]
    if not is_product_url(url):
        print(f"⏭️ Skipping non-product URL ({i+1}): {url}")
        continue
 
    print(f"🔍 Scraping {i+1}/{len(urls)}: {url}")
    proxy = generate_proxy()
    driver = create_driver(proxy)
 
    result = scrape_with_retries(driver, url)
    df_output.loc[len(df_output)] = result
    df_output.to_excel(output_file, index=False)
 
    with open(progress_file, 'w') as f:
        f.write(str(i + 1))
 
    driver.quit()
    time.sleep(random.uniform(2, 4))
 
print(f"\n✅ Scraping complete. All data saved to: {output_file}")
 