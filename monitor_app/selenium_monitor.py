import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
import time 
import pandas as pd
import pickle
from selenium.common.exceptions import StaleElementReferenceException
from monitor_app.slack_api import SlackAgent


class SeleniumMonitor(webdriver.Chrome):
    def __init__(self, threshold) -> None:
        self.SlackAgentInstance = SlackAgent()
        self.threshold = threshold
        self.minute_cooldown = datetime.datetime.now() - datetime.timedelta(minutes=6)
        self.hourly_cooldown = datetime.datetime.now() - datetime.timedelta(hours=1, minutes=1)

        options = webdriver.ChromeOptions()
        user_profile = "/Users/berkayg/Codes/testing/custom_chrome_profile/Default"

        options.add_argument("--headless")
        # options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1280,1080")
        # user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36"
        options.add_argument(f"--user-agent={user_agent}")

        options.add_argument(f'--profile-directory={user_profile}')
        options.add_argument("--remote-debugging-port=9222")

        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("excludeSwitches", [
                                        "enable-automation", "ignore-certificate-errors", "enable-logging"])
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument("--disable-extensions")
        options.add_argument("--dns-prefetch-disable")
        options.add_argument("--disable-gpu")
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)
        super(SeleniumMonitor, self).__init__("/app/.chromedriver/bin/chromedriver", options=options)
        self.get("https://www.tradingview.com/crypto-screener/")
        time.sleep(5)
        self._add_cookie()


    def _add_cookie(self):
        with open("cookies.pkl", "rb") as rd:
            cookies = pickle.load(rd)

        for cookie in cookies:
            self.add_cookie(cookie)
        self.refresh()
        time.sleep(5)


    def read_table(self):
        container = "tv-data-table__tbody"
        target_path = f"//tbody[@class='{container}']//tr"
        symbols = self.find_elements(by=By.XPATH, value=target_path)
        symbols_length = len(symbols)
        value_dict = {}
        for idx in range(symbols_length):
            try:
                target_path = f"//tbody[@class='{container}']//tr[{idx + 1}]"
                symbol = self.find_element(by=By.XPATH, value=target_path).text
            except StaleElementReferenceException:
                target_path = f"//tbody[@class='{container}']//tr[{idx + 1}]"
                symbol = self.find_element(by=By.XPATH, value=target_path).text
            value = {symbol.split("\n")[0]: symbol.split("\n")[-1].split(" ")}
            value_dict.update(value)

        df = pd.DataFrame(value_dict, index=["price", "change_1h", "change_5min"]).T
        df = df.applymap(lambda x: float(x.strip().replace("%", "").replace("−", "")))
        return df

    def calculate_stats(self, df, threshold=5):
        last_5_min = df.loc[df["change_5min"] > threshold, "change_5min"]
        last_1_hour = df.loc[df["change_1h"] > threshold, "change_1h"]

        if last_5_min.shape[0] > 0 and (datetime.datetime.now() - self.minute_cooldown).total_seconds() >= (60 * 5) + 15:
            last_5_min = last_5_min.map(lambda x: f"%{round(abs(x), 1)} düştü:arrow_down:" if max(0, x) == 0 else f"%{round(abs(x), 1)} arttı:arrow_up:")
            entry_edit = ":right_anger_bubble:*SON 5 DAKİKADA*\n" + last_5_min.to_string() + "\n" + " - " * 15
            self.minute_cooldown = datetime.datetime.now()
            print(self.minute_cooldown)
            print(entry_edit)

            self.SlackAgentInstance.send_alert(
                text=entry_edit, channel=self.slack_channel
            )
            

        elif last_1_hour.shape[0] > 0 and (datetime.datetime.now() - self.hourly_cooldown).total_seconds() >= (60 * 60) + 15:
            last_1_hour = last_1_hour.map(lambda x: f"%{round(abs(x), 1)} düştü:arrow_down:" if max(0, x) == 0 else f"%{round(abs(x), 1)} arttı:arrow_up:")
            entry_edit = ":right_anger_bubble:*SON 1 SAATTE*\n" + last_1_hour.to_string() + "\n" + " - " * 15
            self.hourly_cooldown = datetime.datetime.now()
            print(self.hourly_cooldown)
            print(entry_edit)
            self.SlackAgentInstance.send_alert(
                text=entry_edit, channel=self.slack_channel
            )

    def start_monitoring(self):
        print("Monitoring Started")
        while True:
            try:
                df = self.read_table()
                print(df)
                _ = self.calculate_stats(df, threshold=self.threshold)
                time.sleep(3)
            except StaleElementReferenceException:
                pass




