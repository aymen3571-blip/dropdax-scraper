import time
import pandas as pd
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. HEADLESS BROWSER SETUP (Required for GitHub) ---
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")

# Install Driver automatically
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Dictionary to keep track of auctions in memory
master_tracker = {}

def clean_price(price_str):
    """Converts '$5,069' to 5069 for better WordPress sorting."""
    return price_str.replace('$', '').replace(',', '').strip()

def apply_settings(wait):
    """
    PROTECTION CODE: Exact logic from your local script.
    """
    print("Applying filters...")
    filter_names = [".com", "AuctionsEndingToday", "AuctionsWithBids", "NoDashes", "NoNumbers"]
    for name in filter_names:
        try:
            checkbox = wait.until(EC.presence_of_element_located((By.NAME, name)))
            if not checkbox.is_selected():
                driver.execute_script("arguments[0].click();", checkbox)
        except: continue
    
    print("Opening Page Size dropdown to 250 items...")
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        dropdown_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "mat-select[role='combobox']")))
        driver.execute_script("arguments[0].click();", dropdown_box)
        time.sleep(2)
        try:
            option_250 = wait.until(EC.element_to_be_clickable((By.ID, "mat-option-3")))
            driver.execute_script("arguments[0].click();", option_250)
        except:
            option_250 = wait.until(EC.element_to_be_clickable((By.XPATH, "//mat-option//span[contains(text(), '250')]")))
            driver.execute_script("arguments[0].click();", option_250)
        
        print("✓ SUCCESS: Page view expanded to 250.")
        time.sleep(5) 
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception as e:
        print(f"Paginator notice: Proceeding with current view.")

def monitor_auctions():
    # --- CLOUD PATH CONFIGURATION ---
    # We save to the current folder so GitHub Actions can find it easily
    save_path = "dropcatch_results.csv"
    
    driver.get("https://www.dropcatch.com")
    wait = WebDriverWait(driver, 20)

    # Initial Run
    apply_settings(wait)

    # --- SAFETY TIMEOUT FOR GITHUB ---
    # We add a max limit so the script doesn't run forever and consume all your free GitHub minutes
    start_time = time.time()
    max_duration = 60 * 60  # 60 minutes max run time

    try:
        while True:
            if time.time() - start_time > max_duration:
                print("⚠️ Max execution time reached. Force saving and exiting.")
                break

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2) 

            domain_anchors = driver.find_elements(By.ID, "domainName")

            # PROTECTION: Page Reset Check
            if len(domain_anchors) == 0:
                print("⚠️ No domains detected! Waiting 5s then re-checking...")
                time.sleep(5)
                domain_anchors = driver.find_elements(By.ID, "domainName")
                if len(domain_anchors) == 0:
                    apply_settings(wait)
                    continue

            print(f"\n--- Scan: {time.strftime('%H:%M:%S')} | Visible Rows: {len(domain_anchors)} ---")
            
            all_ended = True 
            found_data_in_loop = False 

            for d_el in domain_anchors:
                try:
                    d_text = d_el.get_attribute("textContent").strip()
                    if not d_text: continue

                    row = d_el.find_element(By.XPATH, "./ancestor::section[1]")
                    p_el = row.find_element(By.ID, "domainPrice")
                    t_el = row.find_element(By.ID, "time-remaining")
                    
                    # --- NEW DATA EXTRACTION ---
                    try:
                        # Find Type by class (Private Seller / Pre-Release)
                        type_el = row.find_element(By.CSS_SELECTOR, ".dc-table-search-results__type")
                        type_text = type_el.get_attribute("textContent").strip()
                    except:
                        type_text = "N/A"

                    try:
                        # Find Bids by ID 'bidCount'
                        bid_el = row.find_element(By.ID, "bidCount")
                        bid_text = bid_el.get_attribute("textContent").strip()
                    except:
                        bid_text = "0"
                    # ---------------------------

                    p_raw = p_el.get_attribute("textContent").strip()
                    t_text = t_el.get_attribute("textContent").strip()
                    p_clean = clean_price(p_raw)

                    found_data_in_loop = True

                    # --- ORIGINAL STUCK TIMER & FROZEN LOGIC ---
                    existing_entry = master_tracker.get(d_text, {})
                    prev_raw_time = existing_entry.get('Raw_Time', '')
                    stuck_count = existing_entry.get('Stuck_Count', 0)

                    if t_text == prev_raw_time and t_text != "Ended":
                        stuck_count += 1
                    else:
                        stuck_count = 0 

                    is_frozen = False
                    if stuck_count >= 5 and "m" not in t_text and "h" not in t_text:
                        is_frozen = True
                        print(f"❄️ Detected Frozen Timer for {d_text} ({t_text}). Marking Finalized.")

                    if "Ended" in t_text or not t_text or len(t_text) < 2 or is_frozen:
                        if is_frozen:
                            status = "Finalized"
                        else:
                            time.sleep(0.5) 
                            try:
                                t_text_check = t_el.get_attribute("textContent").strip()
                                if t_text_check and "Ended" not in t_text_check and len(t_text_check) > 2:
                                    status = "Active"
                                    all_ended = False
                                    stuck_count = 0
                                else:
                                    status = "Finalized"
                            except:
                                status = "Finalized"
                    else:
                        status = "Active"
                        all_ended = False

                    # Update master list (Added Type and Bids)
                    master_tracker[d_text] = {
                        "Price": p_clean, 
                        "Status": status, 
                        "Type": type_text,     # NEW
                        "Bids": bid_text,      # NEW
                        "Raw_Time": t_text,       
                        "Stuck_Count": stuck_count, 
                        "Date": time.strftime("%Y-%m-%d")
                    }
                    
                    if status == "Finalized":
                        print(f"✅ SOLD: {d_text} | {p_clean}")
                    else:
                        print(f"🕒 {d_text} | {p_clean} | {type_text} | {bid_text} bids")

                except Exception:
                    continue

            # --- CSV UPDATE (CLEAN FORMAT FOR WORDPRESS) ---
            if len(master_tracker) > 0:
                clean_list = [{
                    "Domain": k, 
                    "Price": v['Price'], 
                    "Status": v['Status'], 
                    "Date": v['Date'],
                    "Type": v.get('Type', 'N/A'), # NEW COLUMN
                    "Bids": v.get('Bids', '0')    # NEW COLUMN
                } for k, v in master_tracker.items()]
                
                df = pd.DataFrame(clean_list)
                df.to_csv(save_path, index=False) 
                print(f"Updated CSV with {len(clean_list)} entries.")

            # --- SMART EXIT ---
            if all_ended and len(domain_anchors) > 0 and found_data_in_loop:
                print("🏁 Auctions finished. Performing final status check...")
                
                for domain in master_tracker:
                    master_tracker[domain]['Status'] = "Finalized"
                
                # Final Clean Save
                final_list = [{
                    "Domain": k, 
                    "Price": v['Price'], 
                    "Status": v['Status'], 
                    "Date": v['Date'],
                    "Type": v.get('Type', 'N/A'),
                    "Bids": v.get('Bids', '0')
                } for k, v in master_tracker.items()]
                
                pd.DataFrame(final_list).to_csv(save_path, index=False)
                print("🏁 SUCCESS: All visible auctions ended. Final report saved.")
                break

            time.sleep(2)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    monitor_auctions()

