import os
import time
import json
import logging
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup logging
logging.basicConfig(
    filename='scraping.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Chrome options
options = uc.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")
options.add_argument("--disable-extensions")
driver = uc.Chrome(options=options)
wait = WebDriverWait(driver, 30)  # More wait time for slow-loading pages

# Resume file
resume_file = "scraped_categories.json"
if os.path.exists(resume_file):
    with open(resume_file, "r") as f:
        scraped_categories = json.load(f)
else:
    scraped_categories = []
all_product_urls = set()

def save_progress(category_url):
    scraped_categories.append(category_url)
    with open(resume_file, "w") as f:
        json.dump(scraped_categories, f)

def wait_for_products():
    try:
        wait.until(EC.presence_of_all_elements_located((By.XPATH, "//*[@id='ajax-show-list']/div/figure")))
    except:
        logging.warning("Timeout waiting for product elements.")
        time.sleep(5)  # Last chance wait

def scrape_products_on_page():
    urls = set()
    wait_for_products()
    figures = driver.find_elements(By.XPATH, "//*[@id='ajax-show-list']/div/figure")
    for fig in figures:
        try:
            a_tag = fig.find_element(By.XPATH, ".//div/div[1]/a")
            href = a_tag.get_attribute("href")
            if href:
                urls.add(href)
        except:
            continue
    return urls

def paginate_and_scrape():
    while True:
        product_links = scrape_products_on_page()
        all_product_urls.update(product_links)
        logging.info(f"Scraped {len(product_links)} URLs on current page.")
        try:
            nav_ul = driver.find_element(By.XPATH, '//*[@id="ajax-show-list"]/nav[1]/ul')
            lis = nav_ul.find_elements(By.TAG_NAME, 'li')
            active_found = False
            next_page_li = None
            for li in lis:
                li_class = li.get_attribute("class")
                if "active" in li_class:
                    active_found = True
                    continue
                if active_found and "disabled" not in li_class and li.text.strip().isdigit():
                    next_page_li = li
                    break
            if next_page_li:
                try:
                    next_btn = next_page_li.find_element(By.TAG_NAME, "a")
                    driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(3)
                    wait_for_products()
                except Exception as e:
                    logging.error("Pagination click failed: " + str(e))
                    break
            else:
                break
        except Exception as e:
            logging.warning("Pagination nav not found or ended: " + str(e))
            break

try:
    driver.get("https://www.serversupply.com/")
    wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/header/nav[2]/div/div[1]/button"))).click()
    time.sleep(2)
    container = driver.find_element(By.XPATH, "/html/body/header/nav[2]/div/div[1]/div")
    category_links = container.find_elements(By.TAG_NAME, "a")
    category_urls = [link.get_attribute("href") for link in category_links if link.get_attribute("href")]
    for category_url in category_urls:
        if category_url in scraped_categories:
            logging.info(f"Skipping already scraped: {category_url}")
            continue
        logging.info(f"🧭 Visiting Category: {category_url}")
        driver.get(category_url)
        time.sleep(3)
        wait_for_products()
        paginate_and_scrape()
        save_progress(category_url)
except Exception as e:
    logging.error("❌ Error during scraping: " + str(e))
finally:
    driver.quit()
df = pd.DataFrame({"Product URL": list(all_product_urls)})
df.to_excel("product_urls.xlsx", index=False)
logging.info(f"✅ Scraping complete. Total URLs scraped: {len(all_product_urls)}")
print(f"✅ Scraping complete. Total URLs scraped: {len(all_product_urls)}")