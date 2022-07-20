#SMS Support
import os,json,logging,time
#Configure logging
logging.basicConfig(level=logging.INFO)

#Beautiful Soup


#import selenium
from selenium import webdriver
import selenium.common.exceptions as exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select

from selenium.webdriver.firefox.options import Options


def punch(transfer=None,clock_in=None,dry_run=True,headless=True,use_config=False,failed=0):
    if clock_in is not None:
        logging.warning(f'Clocking {clock_in}')
    cred = json.load(open('credentials.json'))
    if dry_run:
        logging.warning("NOTE: This is a DRY RUN! No punching will occur!")
    elif transfer is None:
        if use_config and 'transfer' in cred:
            transfer = cred['transfer']
        else:
            logging.warning("No transfer is selected! Defaulting to dry_run")
            dry_run=True
    options = Options()
    if headless:
        options.add_argument("--headless")        
    driver = webdriver.Firefox(options=options)

    def waitFor(key,selector=By.CSS_SELECTOR,parent=driver,delay=10):
        return WebDriverWait(parent,delay).until(EC.visibility_of_element_located((selector,key)))
    def waitText(text,parent=driver,tag='*',delay=5):
        return waitFor(f"//{tag}[contains(., '{text}')]",selector=By.XPATH,parent=parent,delay=delay)

    kronos = cred['kronos_entrypoint']
    driver.get(kronos)
    try:
        #Select College
        logging.info("Selecting college")
        waitFor("#selCollege").click() #Select dropdown
        waitFor("#selCollege > option:nth-child(3)").click() #Click CGU
        waitFor("#list-providers > ul:nth-child(1) > li:nth-child(4) > a:nth-child(1)").click() #Click submit

        #Microsoft Login
        logging.info("Logging into OAuth/Microsoft")
        email = waitFor("#i0116")
        email.click()
        email.send_keys(cred['email'])
        waitFor("#idSIButton9").click() #Submit email
        password = waitFor("#i0118")
        password.click()
        password.send_keys(cred['password'])
        waitFor("#idSIButton9").click() #Finish login
        logging.warning("Sent Two-Factor Authentication to device!")
        waitText('Stay signed in?',delay=60*3) #Wait for 2FA
    except exceptions.TimeoutException as e:
        logging.error("2FA FAILED!")
        driver.close()        
        return "2FA_FAILED"
    try:
        waitFor("#idSIButton9").click() #Finish 2FA
        logging.info("2FA Completed! Waiting for kronos to load.")

        #KRONOS
        ele = waitFor("#widgetFrame694")
        driver.switch_to.frame(ele)
        
        if clock_in=="in":
            logging.info(f"Kronos loaded; Selecting transfer {transfer}")
            #Selects transfer
            waitFor("i.caret-down:nth-child(1)").click()
            options = waitFor(".search-options")
            if transfer is not None and not dry_run:
                #Punch In
                waitText(transfer,tag="a").click()
                logging.warning("Punching timecard!")
                time.sleep(1)
                waitText("Record Timestamp",tag="button").click()
                time.sleep(1)                
            else:
                logging.warning("No transfer, not selecting")
        elif clock_in=="out" and not dry_run:
            #Punch Out
            time.sleep(1)
            logging.warning("Punching timecard!")
            waitText("Record Timestamp",tag="button").click()
            time.sleep(1)
            
        logging.info("Done.")
    except exceptions.TimeoutException as e:
        logging.error("PUNCH FAILED")
        driver.close()
        return "FAILED_PUNCH"
    return driver


def diagnostic(driver=None):
    if driver is None:
        driver = punch()
        if isinstance(driver,str): return driver
    def waitFor(key,selector=By.CSS_SELECTOR,parent=driver,delay=10):
        return WebDriverWait(parent,delay).until(EC.visibility_of_element_located((selector,key)))
    def waitText(text,parent=driver,tag='*',delay=5):
        return waitFor(f"//{tag}[contains(., '{text}')]",selector=By.XPATH,parent=parent,delay=delay)
    try:
        driver.switch_to.default_content()
        timecard_frame = waitFor("#widgetFrame783")
        driver.switch_to.frame(timecard_frame)
        printer = waitFor(".icon-k-print")
        printer.click()
        driver.switch_to.window(driver.window_handles[1])
        container = waitFor('.printTblWrap')
        html = container.get_attribute('innerHTML')
        soup = BeautifulSoup(html,'html.parser')
        driver.close()
        data = []
        rows = soup.find('tbody').find_all('tr')
        for row in rows:
            cells = [c.text.strip() for c in row.find_all('td') if c.text.strip() != '']
            data.append(cells)
        return data
    except exceptions.TimeoutException as e:
        logging.error("Failed to find element!")
        return "FAILED_DIAG"
    return "FAILED_DAIG_OTHER"
        
if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Autopunch Kronos based on a transfer and delay')
    parser.add_argument('punch_type', choices=("in","out"),help="Punch in or punch out?")
    parser.add_argument('transfer', type=int, help="The tranfer to punch")
    parser.add_argument('delay', type=int, nargs="?", help="Hours to clock.",default=1)
    parser.add_argument('--window', action='store_false', help="Run in windowed mode")
    parser.add_argument('--dry', action='store_true', help="Dry-run; don't actually punch.")
    args = parser.parse_args()
    driver = punch(args.transfer,clock_in=args.punch_type,dry_run=args.dry,headless=args.window)
    try:
        driver.close()
    except Exception as e:
        raise e

