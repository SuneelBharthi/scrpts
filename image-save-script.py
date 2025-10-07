import os
import time
import csv
import re
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# === CLEAN MPN FUNCTION ===
def clean_mpn(raw_mpn):
    if raw_mpn:
        clean = re.sub(r'^mpn:?-?', '', raw_mpn.lower())  # remove prefix
        clean = re.sub(r'[^\w\-_\.]', '-', clean)         # keep only safe characters
        clean = re.sub(r'-+', '-', clean)                 # replace multiple dashes
        return clean.strip('-')
    return 'unknown'

# === DOWNLOAD IMAGE FUNCTION ===
def download_image(img_url, mpn, label, is_thumbnail=False):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(img_url, headers=headers, timeout=10)
        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            os.makedirs("product_images", exist_ok=True)
            cleaned_mpn = clean_mpn(mpn)
            if is_thumbnail:
                filename = f"{cleaned_mpn}-price.jpg"
            else:
                filename = f"{cleaned_mpn}-{label}-price.jpg"

            filepath = os.path.join("product_images", filename.lower())
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"✅ Saved: {filename}")
            return filename.lower()
        else:
            print(f"❌ Skipped (not image or forbidden): {img_url}")
    except Exception as e:
        print(f"❌ Error downloading image: {img_url} | {e}")
    return None

# === SCRAPE IMAGES FUNCTION ===
def scrape_images(driver, mpn):
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="image-0"]/img'))
        )
        image_elements = driver.find_elements(By.XPATH,
            '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[1]/div/div[1]/div[1]/div/app-custom-pdp-swiper/div[2]/div[2]//img'
        )
        downloaded = []
        for i, img_tag in enumerate(image_elements[:4]):
            img_url = img_tag.get_attribute('src') or img_tag.get_attribute('data-src')
            if img_url:
                if i == 0:
                    img_name = download_image(img_url, mpn, label="price", is_thumbnail=True)
                else:
                    img_name = download_image(img_url, mpn, label=str(i), is_thumbnail=False)
                downloaded.append(img_name if img_name else "")
        return downloaded
    except Exception as e:
        print(f"❌ Image scraping error for {mpn} | {e}")
        return ["", "", "", ""]

# === GET MPN FUNCTION ===
def extract_mpn(driver):
    try:
        try:
            mpn_element = driver.find_element(By.XPATH,
                '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[1]/div/div[1]/div[2]/div[1]/div[1]/span'
            )
        except:
            mpn_element = driver.find_element(By.XPATH,
                '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[1]/div/div[1]/div[2]/div[1]/div[1]'
            )
        mpn = mpn_element.text.strip().lower().replace(" ", "-")
        if not mpn or "£" in mpn or "inc" in mpn or len(mpn) > 50:
            raise ValueError("Likely not a valid MPN")
        return mpn
    except:
        fallback = f"unknown-{int(time.time())}"
        print(f"⚠️ Fallback MPN: {fallback}")
        return fallback

# === MAIN FUNCTION ===
def main():
    product_urls = [
        "https://box.co.uk/asus-dual-rtx5060ti-o8g-90yv0mp2-m0na00",
        "https://box.co.uk/rx9070-16g-l-oc-powercolor-hellhound-16gb-oc-gaming",
        "https://box.co.uk/hw-q600c-xu-samsung-q600c-q-symphony-3-1-2-soundbar",
        "https://box.co.uk/hw-q800d-xu-samsung-q800d-q-symphony-5-1-2-soundbar",
        "https://box.co.uk/hw-s60d-xu-samsung-s60d-5-0ch-lifestyle-aio-soundbar",
        "https://box.co.uk/27m2n3200a-00-philips-evnia-27m2n3200a-00-27-fhd-ips",
        "https://box.co.uk/ag275qxn-eu-aoc-agon-27-quad-hd-va-led-165hz-gaming",
        "https://box.co.uk/32m2c3500l-00-philips-evnia-quad-hd-va-gaming-monitor",
        "https://box.co.uk/cu34v5cw-bk-aoc-v5-34in-wide-quad-hd-va-led",
        "https://box.co.uk/32m2c5500w-00-philips-evnia-31-5-qhd-va-curved",
        "https://box.co.uk/34m2c8600-00-philips-evnia-34-wqhd-oled-curved",
        "https://box.co.uk/32m2n8900-00-philips-evnia-8000-31-5-4k-uhd-oled",
        "https://box.co.uk/cu34g2xp-bk-aoc-g2-cu34g2xp-bk-34-ultrawqhd-va-led",
        "https://box.co.uk/q27g2e-bk-aoc-g2-27in-qhd-va-155hz-gaming-monitor",
        "https://box.co.uk/philips-346e2cuae-34-curved-wqhd-100hz-usb-c-height-adjustable-monitor",
        "https://box.co.uk/346e2lae-00-philips-e-line-34in-wqhd-va-100hz-monito",
        "https://box.co.uk/34e1c5600he-00-philips-5000-series-34in-wqhd-va",
        "https://box.co.uk/32e1n1800la-00-philips-1000-31-5-in-4k-monitor",
        "https://box.co.uk/24m2n3200a-00-philips-evnia-full-hd-ips-gaming-monitor",
        'https://box.co.uk/273v7qjab-00-philips-27-v-line-fhd-ips-lcd-monitor',
        'https://box.co.uk/27m2c5200w-00-philips-evnia-27-fhd-va-curved-gaming',
        'https://box.co.uk/27e1n1300a-00-philips-27e1n1300a-00-27-fhd-ips-lcd',
        'https://box.co.uk/271e1sca-00-philips-e-line-271e1sca-00-27-fhd-va-lcd',
        'https://box.co.uk/27m2c5501-00-philips-evnia-5000-27-quad-hd',
        'https://box.co.uk/27m2n3201a-00-philips-evnia-27-in-full-hd-monitor',
        'https://box.co.uk/24m2n3201a-00-philips-evnia-23-8-in-full-hd-monitor',
        'https://box.co.uk/49m2c8900-00-philips-evnia-48-9-dual-qhd-oled-curved',
        'https://box.co.uk/24e1n1100a-00-philips-1000-series-23-8-fhd-ips-flat',
        'https://box.co.uk/346b1c-00-philips-b-line-wqhd-lcd-curved-monitor',
        'https://box.co.uk/34m2c6500-00-philips-evnia-wide-quad-hd-oled-gaming-monitor',
        'https://box.co.uk/328e1ca-00-philips-e-line-328e1ca-00-31-5-4k-uhd-va',
        'https://box.co.uk/241e1sc-00-philips-e-line-23-6-fhd-freesync-monitor',
        'https://box.co.uk/27m2n3500nl-00-philips-evnia-quad-hd-va-gaming-monitor',
        'https://box.co.uk/c32g2ze-bk-aoc-c32g2ze-bk-31-5-fhd-va-led-freesync',
        'https://box.co.uk/u32g3x-bk-aoc-u32g3x-bk-31-5-4k-ultra-hd-ips-led',
        'https://box.co.uk/mxpn3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-128gb',
        'https://box.co.uk/apple-mac-mini-a2686-m2-8gb-512gb-desktop-pc',
        'https://box.co.uk/mtpd3zd-a-apple-iphone-15-15-5-cm-6-1-inch-dual',
        'https://box.co.uk/mu1j3zd-a-apple-iphone-15-plus-17-cm-6-7-inch-dual',
        'https://box.co.uk/muwa3zm-a-apple-bluetooth-stylus-pencil-white',
        'https://box.co.uk/mgn63b-a-apple-macbook-air-2020-m1-8gb-256gb',
        'https://box.co.uk/mc8n4b-a-apple-macbook-air-13-inch-m3-chipset-24gb',
        'https://box.co.uk/mx313b-a-apple-macbook-pro-16-in-m4-max-chipset-48gb',
        'https://box.co.uk/mx2j3b-a-apple-macbook-pro-14-in-m4-pro-chipset-24gb',
        'https://box.co.uk/mx2x3b-a-apple-macbook-pro-16-in-m4-pro-chipset-24gb',
        'https://box.co.uk/mx2k3b-a-apple-macbook-pro-14-in-m4-max-chipset-36gb',
        'https://box.co.uk/mw2x3b-a-apple-macbook-pro-14-inch-m4-chipset-16gb',
        'https://box.co.uk/mc7x4b-a-apple-macbook-air-13-inch-m2-chipset-16gb',
        'https://box.co.uk/mx2t3b-a-apple-macbook-pro-16-in-m4-pro-chipset-24gb',
        'https://box.co.uk/mx2y3b-a-apple-macbook-pro-16-in-m4-pro-chipset-48gb',
        'https://box.co.uk/mx2g3b-a-apple-macbook-pro-14-in-m4-max-chipset-36gb',
        'https://box.co.uk/mx303b-a-apple-macbook-pro-16-in-m4-max-chipset-36gb',
        'https://box.co.uk/mx2h3b-a-apple-macbook-pro-14-in-m4-pro-chipset-24gb',
        'https://box.co.uk/mx2u3b-a-apple-macbook-pro-16-in-m4-pro-chipset-48gb',
        'https://box.co.uk/mc9j4b-a-apple-macbook-air-15-inch-m3-chipset-24gb',
        'https://box.co.uk/mx2f3b-a-apple-macbook-pro-14-in-m4-pro-chipset-24gb',
        'https://box.co.uk/mc9f4b-a-apple-macbook-air-15-inch-m3-chipset-16gb',
        'https://box.co.uk/mc9k4b-a-apple-macbook-air-15-inch-m3-chipset-24gb',
        'https://box.co.uk/mx2e3b-a-apple-macbook-pro-14-in-m4-pro-chipset-24gb',
        'https://box.co.uk/mc8p4b-a-apple-macbook-air-13-inch-m3-chipset-24gb',
        'https://box.co.uk/243v7qjabf-00-philips-v-line-243v7qjabf-00-23-8-fhd',
        'https://box.co.uk/32e1n3100la-00-philips-3000-31-5-in-full-hd-monitor',
        'https://box.co.uk/27b2g5500-00-philips-27-quad-hd-ips-monitor',
        'https://box.co.uk/h610m-hvs-m-2-r2-0-asrock-intel-ddr4-1700-motherboard',
        'https://box.co.uk/27g2zn3-bk-aoc-g2-27g2zn3-bk-27-fhd-fast-va-lcd',
        'https://box.co.uk/27g2spae-bk-aoc-c2-27g2spae-bk-27-fhd-ips-led',
        'https://box.co.uk/ag275qzn-eu-aoc-agon-5-27in-qhd-va-240hz-gaming',
        'https://box.co.uk/mrxv3b-a-ag-apple-macbook-air-m3-octa-core-chip-8gb',
        'https://box.co.uk/mc8k4b-a-ag-apple-macbook-air-13-laptop-m3-octa-core',
        'https://box.co.uk/rfb-sm-s906b-ds-samsung-galaxy-s22-8gb-smartphone',
        'https://box.co.uk/mlpg3b-a-ag-apple-iphone-13-a15-bionic-chip-128gb',
        'https://box.co.uk/mye73qn-a-ag-apple-iphone-16-a18-chip-128gb-6-1',
        'https://box.co.uk/sm-s928b-ds-ag-samsung-galaxy-s24-ultra5g-smartphone',
        'https://box.co.uk/kf432s20ibk2-64-kingston-technology-64gb-ddr4',
        'https://box.co.uk/kvr32s22d8-16-kingston-technology-valueram-16gb',
        'https://box.co.uk/kf432s20ibk2-32-kingston-technology-32gb-ddr4',
        'https://box.co.uk/kcp432sd8-16-kingston-technology-16gb-sodimm',
        'https://box.co.uk/kvr32s22s8-16-kingston-technology-ddr4-sodimm',
        'https://box.co.uk/kvr32s22d8-32-kingston-technology-valueram-32gb',
        'https://box.co.uk/32m2c5501-00-philips-evnia-32-curved-fhd-monitor',
        'https://box.co.uk/34m2c3500l-00-phillips-evnia-34-wqhd-180hz-curved',
        'https://box.co.uk/32m2n6800m-00-philips-evnia-31-5-ips-lcd-4k-ultra-hd',
        'https://box.co.uk/27m2n5500-00-philips-evnia-27-in-quad-hd-monitor',
        'https://box.co.uk/42m2n8900-00-philips-evnia-41-5-4k-uhd-oled-flat',
        'https://box.co.uk/27m2c5500w-00-philips-evnia-27-qhd-va-curved-gaming',
        'https://box.co.uk/49m2c8900l-00-philips-evnia-8000-48-9-dual-qhd-oled',
        'https://box.co.uk/27m2c5201l-00-philips-evnia-5000-27-fhd-1ms-monitor',
        'https://box.co.uk/27m2n8500-00-philips-evnia-quad-hd-oled-gaming-monitor',
        'https://box.co.uk/34m2c6500-00-ag-philips-evnia-curved-oled-monitor',
        'https://box.co.uk/rx9060-xt-16g-l-oc-powercolor-radeon-rx-9060-xt',
        'https://box.co.uk/rx9070-16g-e-oc-powercolor-red-devil-16gb-oc-gaming',
        'https://box.co.uk/rx9070xt-16g-e-oc-powercolor-red-devil-16g-oc-gaming',
        'https://box.co.uk/mag-27cq6f-msi-mag-mag-27cq6f-quad-hd-monitor',
        'https://box.co.uk/hw-b650d-xu-samsung-b650d-3-1ch-370w-soundbar',
        'https://box.co.uk/hw-s50b-xu-samsung-s-series-hw-s50b-3-0-soundbar',
        'https://box.co.uk/hw-q930d-xu-samsung-q930d-q-symphony-9-1-4-soundbar',
        'https://box.co.uk/kingston-technology-fury-kf432c16bbk2-64',
        'https://box.co.uk/kf432c16bb-8-kingston-technology-fury-beast',
        'https://box.co.uk/kingston-technology-fury-beast-kf432c16bb1k2-32',
        'https://box.co.uk/241b7qupbeb-00-bd-philips-b-line-23-8-full-monitor',
        'https://box.co.uk/24e1n1300ae-00-bd-philips-1000-fhd-ips-led-monitor',
        'https://box.co.uk/25m2n5200p-00-ag-philips-evnia-25m2n5200p-00-monitor',
        'https://box.co.uk/u27g3x-bk-ag-aoc-g3-u27g3x-4k-uhd-gaming-monitor',
        'https://box.co.uk/mqrn3b-a-ag-apple-imac-m3-chip-8gb-ram-256gb-pc',
        'https://box.co.uk/mvx53nf-a-ag-apple-ipad-pro-13-a2925-512gb-silver',
        'https://box.co.uk/mv6w3nf-a-ag-apple-ipad-air-13-apple-m2-8gb-tablet',
        'https://box.co.uk/mvx23nf-a-bd-apple-ipad-pro-m4-7th-gen-13-tablet',
        'https://box.co.uk/rfb-mnxk3b-a-apple-ipad-pro-m2-16gb-wi-fi-tablet',
        'https://box.co.uk/muwl3nf-a-ag-apple-ipad-air-11-2024-apple-m2-8gb-ram',
        'https://box.co.uk/a620m-hdv-m-2-asrock-motherboard-micro-atx',
        'https://box.co.uk/b450m-ac-r2-0-asrock-micro-atx-am4-motherboard',
        'https://box.co.uk/90ai00n0-bcs120-asus-zenfone-11-ultra-rhinoshield',
        'https://box.co.uk/md2t4b-a-apple-imac-m4-24gb-512gb-24-aio-pc-blue',
        'https://box.co.uk/mwug3b-a-apple-imac-m4-16gb-256gb-24-aio-pc-pink',
        'https://box.co.uk/mwuf3b-a-apple-imac-m4-16gb-256gb-24-aio-pc-blue',
        'https://box.co.uk/mwv03b-a-apple-imac-m4-16gb-512gb-24-aio-pc-green',
        'https://box.co.uk/mpw43zd-a-apple-iphone-14-15-5-cm-6-1-inch-dual',
        'https://box.co.uk/mqru3b-a-apple-imac-a2873-8gb-512gb-24-all-in-one-pc',
        'https://box.co.uk/apple-mac-studio-a2901-m2-ultra-64gb-1tb-desktop-pc',
        'https://box.co.uk/md2q4b-a-apple-imac-m4-24gb-512gb-24-aio-pc-green',
        'https://box.co.uk/mqrp3b-a-apple-imac-a2873-m3-8gb-512gb-ssd-24-aio-pc',
        'https://box.co.uk/mwuc3b-a-apple-imac-m4-16gb-256gb-24-aio-pc-silver',
        'https://box.co.uk/mqrq3b-a-apple-imac-a2873-8gb-256gb-ssd-24-aio-pc',
        'https://box.co.uk/mcx44b-a-apple-mac-mini-m4-pro-24gb-512gb-macos-pc',
        'https://box.co.uk/mwuy3b-a-apple-imac-m4-16gb-256gb-24-aio-pc-green',
        'https://box.co.uk/mqrt3b-a-apple-imac-chip-8gb-256gb-24-all-in-one-pc',
        'https://box.co.uk/mqrr3b-a-apple-imac-a2873-m3-8gb-ram-512gb-24-aio-pc',
        'https://box.co.uk/mwue3b-a-apple-imac-m4-16gb-256gb-24-aio-pc-green',
        'https://box.co.uk/kingston-technology-datatraveler-dtxon-128gb',
        'https://box.co.uk/kingston-technology-datatravelerexodia-dtx-256gb',
        'https://box.co.uk/kingston-technology-dt-exodia-m-usb-dtxm-64gb',
        'https://box.co.uk/kingston-technology-128gb-dtduo3cg3-128gb',
        'https://box.co.uk/kingston-technology-kingston-dtmc3g2-128gb',
        'https://box.co.uk/kingston-technology-datatraveler-kyson-dtkn-128gb',
        'https://box.co.uk/kingston-technology-128gb-dt-exodia-m-dtxm-128gb',
        'https://box.co.uk/kingston-technology-datatraveler-dtse9g3-256gb',
        'https://box.co.uk/kingston-technology-datatraveler-dtx-128gb',
        'https://box.co.uk/dtse9g3-64gb-kingston-technology-datatraveler',
        'https://box.co.uk/kingston-technology-datatraveler-kyson-dtkn-64gb',
        'https://box.co.uk/kingston-technology-datatraveler-exodia-dtx-64gb',
        'https://box.co.uk/kingston-technology-kingston-dtmc3g2-256gb',
        'https://box.co.uk/kingston-technology-datatraveler-dtse9g3-128gb',
        'https://box.co.uk/kingston-technology-128gb-usb-flash-drive-datatraveler-70-usb-c-3-2-black',
        'https://box.co.uk/kingston-technology-kingston-dtmc3g2-64gb',
        'https://box.co.uk/kingston-technology-datatraveler-dtduo3cg3-256gb',
        'https://box.co.uk/kingston-technology-kingston-dtduo3cg3-64gb',
        'https://box.co.uk/kingston-technology-datatraveler-dtxon-256gb',
        'https://box.co.uk/kingston-technology-datatraveler-dtse9g3-512gb',
        'https://box.co.uk/kingston-technology-datatraveler-dtmaxa-256gb',
        'https://box.co.uk/kingston-technology-datatraveler-onyx-dtxon-64gb',
        'https://box.co.uk/kingston-nv3-4tb-m-2-nvme-pcie-4-0-ssd-solid-state-drive',
        'https://box.co.uk/kingston-kc600-512gb-skc600-512g',
        'https://box.co.uk/kingston-technology-fury-renegade-4tb-sfyrd-4000g',
        'https://box.co.uk/mcyt4b-a-apple-apple-m-m4-24-gb',
        'https://box.co.uk/mxnc3nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-256gb',
        'https://box.co.uk/mxpp3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-128gb',
        'https://box.co.uk/myhe3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-512gb',
        'https://box.co.uk/mvx53nf-a-apple-ipadpro13-a2925-m4-13in-512gb-silver',
        'https://box.co.uk/mxpy3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-256gb',
        'https://box.co.uk/myh33nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-512gb',
        'https://box.co.uk/mxpx3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-256gb',
        'https://box.co.uk/mxn73nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-128gb',
        'https://box.co.uk/mygy3nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-512gb',
        'https://box.co.uk/mxn93nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-128gb',
        'https://box.co.uk/mxpr3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-128gb',
        'https://box.co.uk/mvvc3nf-a-apple-ipadpro11-a2836-m4-11in-512gb-black',
        'https://box.co.uk/mxpt3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-256gb',
        'https://box.co.uk/mxna3nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-256gb',
        'https://box.co.uk/mxnd3nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-256gb',
        'https://box.co.uk/mxpq3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-128gb',
        'https://box.co.uk/mxpw3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-256gb',
        'https://box.co.uk/myhc3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-512gb',
        'https://box.co.uk/myhf3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-512gb',
        'https://box.co.uk/myhd3nf-a-apple-ipad-mini-a2995-a17-pro-8-3in-512gb',
        'https://box.co.uk/mxn83nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-128gb',
        'https://box.co.uk/mxne3nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-256gb',
        'https://box.co.uk/myh13nf-a-apple-ipad-mini-a2993-a17-pro-8-3in-512gb',
        'https://box.co.uk/mrx73b-a-apple-macbook-pro-m3-pro-12core-chip-18gb',
        'https://box.co.uk/mrw13b-a-apple-macbook-pro-m3-pro-12core-chip-18gb'    ]

    options = Options()
    options.add_argument("--headless=new")  # run headless
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")
    options.page_load_strategy = 'eager'
    options.add_argument("user-agent=Mozilla/5.0")

    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.popups": 2,
        "profile.default_content_setting_values.cookies": 2,
        "profile.managed_default_content_settings.javascript": 1
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    results = []

    for url in product_urls:
        print(f"\n🔍 Scraping: {url}")
        driver.get(url)
        time.sleep(2)

        mpn = extract_mpn(driver)
        print(f"📦 MPN: {mpn}")

        images = scrape_images(driver, mpn)
        images += [""] * (4 - len(images))  # ensure list has 4 items

        results.append({
            "Product_URL": url,
            "Thumbnail_Image": images[0],
            "Additional_Image_1": images[1],
            "Additional_Image_2": images[2],
            "Additional_Image_3": images[3]
        })

    driver.quit()

    # ✅ Save to CSV
    csv_file = "image_data.csv"
    with open(csv_file, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ All done. Data saved to: {csv_file}")

if __name__ == "__main__":
    main()
