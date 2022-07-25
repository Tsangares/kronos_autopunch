import os,json,logging,time,random
logging.basicConfig(level=logging.INFO)
from FirefoxDriver import FirefoxDriver
import selenium.common.exceptions as exceptions
from bs4 import BeautifulSoup

class Kronos(FirefoxDriver):
    entry_url = "https://timekeeping.claremont.edu/"
    
    CAS_DROPDOWN = "#selCollege"
    CAS_DROPDOWN_CGU = "#selCollege > option:nth-child(3)"
    CAS_SUBMIT = "#list-providers > ul:nth-child(1) > li:nth-child(4) > a:nth-child(1)"

    MICROSOFT_EMAIL = "#i0116"
    MICROSOFT_PASS = "#i0118"
    MICROSOFT_SUBMIT = "#idSIButton9"

    KRONOS_TRANSFER_FRAME = "#widgetFrame694"
    KRONOS_TRANSFER_CARET = "i.caret-down:nth-child(1)"
    KRONOS_TRANSFER_DROPDOWN = ".search-options"
    KRONOS_TRANSFER_SUBMIT = ".krn-button"
    KRONOS_TIMECARD_FRAME = "#widgetFrame783"
    KRONOS_PRINT_ICON = ".icon-k-print"
    KRONOS_PRINT_CONTAINER = ".printTblWrap"
    
    def __init__(self,headless=True,dry_run=True,persist=False,config="config.json"):
        super().__init__(headless,dry_run)
        self.config=json.load(open(config)) if os.path.isfile(config) else None
        self.logged_in = False
        self.persist=persist
        self._last_active = time.time()
        if dry_run:
            logging.info("This is a dry run: no punching will occur.")
      
    def setActive(self):
        self.last_modified = time.time()
    def getLastActive(self):
        minute = (time.time() - self._last_active)/60
        return minute
    def isIdle(self):
        if getLastActive() >= 30:
            logging.info("Have been idle longer than 30 min")
            return True
        try:
            logged_out = self.waitText("Logout successful",timeout=1/60)
            logging.info("At logout screen")
            return True
        except exceptions.TimeoutException as e:
            pass
        logging.info("Not idle; still logged in.")
        return False
    
    def safeQuit(self,error):
        logging.error(error)
        self.quit()
        return error
    
    #Microsoft & 2FA
    def login(self):
        self.get(self.entry_url)
        if self.logged_in and not self.isIdle():
            logging.info("Already logged in!")
            return
        
        
        try: ##Central Authentication Service
            logging.info("CAS: Selecting CGU")
            self.waitFor(self.CAS_DROPDOWN).click()
            self.waitFor(self.CAS_DROPDOWN_CGU).click()
            self.waitFor(self.CAS_SUBMIT).click()
        except exceptions.TimeoutException as e:
            return self.safeQuit("CAS: Failed to select school.")
        
        try: ## Email
            logging.info("Microsoft: Logging in")            
            email = self.waitFor(self.MICROSOFT_EMAIL)
            email.click()
            email.send_keys(self.config['email'])
            self.waitFor(self.MICROSOFT_SUBMIT).click()
            logging.info("Microsoft: Submitted email.")
        except exceptions.TimeoutException as e:
            return self.safeQuit("Microsoft: Failed to submit email.")

        try: ## Password
            password = self.waitFor(self.MICROSOFT_PASS)
            password.click()
            password.send_keys(self.config['password'])
            self.waitFor(self.MICROSOFT_SUBMIT).click()
            logging.info("Microsoft: Submitted password.")
        except exceptions.TimeoutException as e:
            return self.safeQuit("Microsoft: Failed to submit password.")

        try: ## 2FA
            logging.info("DUO: Waiting for 2FA")
            self.waitText('Stay signed in?',timeout=60*3)
            self.waitFor(self.MICROSOFT_SUBMIT).click()
            self.logged_in=True
            logging.info("Logged in.")
        except exceptions.TimeoutException as e:
            return self.safeQuit("DUO: Failed to recieve 2FA!")
        
    #Kronos interface
    def focus_transfer_frame(self):
        try:
            self.switch_to.default_content()            
            frame = self.waitFor(self.KRONOS_TRANSFER_FRAME,timeout=30)
            self.switch_to.frame(frame)
        except exceptions.TimeoutException as e:
            return self.safeQuit("Kronos: Failed to find transfer frame!")

    def timesheet_select_transfer(self,transfer):
        logging.info(f"Kronos: Clocking in transfer {transfer}.")
        try:
            self.waitFor(self.KRONOS_TRANSFER_CARET).click()
            options = self.waitFor(self.KRONOS_TRANSFER_DROPDOWN)
            self.waitText(transfer,tag="a").click()
            return self.punch()
        except exceptions.TimeoutException as e:
            return self.safeQuit("Kronos: Failed to select transfer!")
        
    def punch(self):
        if not self.dry_run:
            try:
                logging.info("Kronos: Punching timecard!")        
                time.sleep(1)
                self.waitText("Record Timestamp",tag="button").click()
                time.sleep(1)
            except exceptions.TimeoutException as e:
                return self.safeQuit("Kronos: Failed to punch")

    def select_printout(self):
        try:
            pass
        except exceptions.TimeoutException as e:
            return self.safeQuit("Kronos: Failed to find printout")
            
    def clock_in(self,transfer):
        response = self.login()
        if isinstance(response,str): return response
        response = self.focus_transfer_frame()
        if isinstance(response,str): return response
        response = self.timesheet_select_transfer(transfer)
        if isinstance(response,str): return response
        if not self.persist:
            self.quit()
        
    def clock_out(self):
        response = self.login()
        if isinstance(response,str): return response
        response = self.focus_transfer_frame()
        if isinstance(response,str): return response
        response = self.punch()
        if isinstance(response,str): return response
        if not self.persist:
            self.quit()
        
    def diag(self):
        response = self.login()
        if isinstance(response,str): return response
        try:
            logging.info("DIAG: Collecting timesheet")
            self.switch_to.default_content()
            logging.info("DIAG: Switching frame")
            timecard_frame = self.waitFor(self.KRONOS_TIMECARD_FRAME)
            self.switch_to.frame(timecard_frame)
            logging.info("DIAG: Clicking print icon")            
            printer = self.waitFor(self.KRONOS_PRINT_ICON)
            printer.click()
            logging.info("DIAG: Changing tabs")
            self.switch_to.window(self.window_handles[1])
            logging.info("DIAG: Collecting table")            
            container = self.waitFor(self.KRONOS_PRINT_CONTAINER,timeout=30)
            logging.info("DIAG: Parsing")
            html = container.get_attribute('innerHTML')
            self.close()
            self.switch_to.window(self.window_handles[0])
            if not self.persist:
                self.quit()
            soup = BeautifulSoup(html,'html.parser')
            return [[c.text.strip() for c in row.find_all('td') if c.text.strip()!=''] for row in soup.find('tbody').find_all('tr')]
        except exceptions.TimeoutException as e:
            return self.safeQuit("DIAG: Failed to get diagnostics")
        
        
if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Autopunch Kronos based on a transfer and delay')
    parser.add_argument('punch_type', choices=("in","out","diag"),help="Punch in or punch out?")
    parser.add_argument('transfer', nargs="?",type=int, help="The tranfer to punch")
    parser.add_argument('--window', action='store_false', help="Run in windowed mode")
    parser.add_argument('--dry', action='store_true', help="Dry-run; don't actually punch.")
    parser.add_argument('--config', type=str, help="Config file location.",default="config.json")
    parser.add_argument('--persist', action='store_true', help="Keep firefox open")
    args = parser.parse_args()
    kronos = Kronos(args.window,args.dry,args.persist,args.config)
    if args.punch_type =="in":
        kronos.clock_in(args.transfer)
    elif args.punch_type =="out":
        kronos.clock_out()
    elif args.punch_type =="diag":
        #kronos.diag()
        kronos.login()
        kronos.diag()
        kronos.diag()
        kronos.diag()
