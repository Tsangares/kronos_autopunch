import random,time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options

class FirefoxDriver(webdriver.Firefox):
    def __init__(self,headless=True,dry_run=True,**kwargs):
        options = Options()
        self.dry_run=dry_run
        if headless:
            options.add_argument("--headless")
        super().__init__(options=options)
    
    def waitFor(self,key,selector=By.CSS_SELECTOR,timeout=10,delay=0.25):
        obj = WebDriverWait(self,timeout).until(EC.visibility_of_element_located((selector,key)))
        time.sleep(abs(random.gauss(2*delay,2*delay)))
        return obj

    def waitText(self,text,tag='*',timeout=5,delay=0.25):
        return self.waitFor(f"//{tag}[contains(., '{text}')]",selector=By.XPATH,delay=delay,timeout=timeout)

