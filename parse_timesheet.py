def parse_timesheet(driver):
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

    
