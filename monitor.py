import requests
import pandas as pd
import datetime
from time import sleep
import os
from slack_api import SlackAgent

# CoinGecko asset ids that will be monitored by the script
SYMBOLS = os.environ['SYMBOLS'].split(",")

# Threshold value after which an alert message will be sent
THRESHOLD = float(os.environ['THRESHOLD'])

# Number of minutes that the script will take into account for Moving Averaging process
LOOKBACK_MINUTES = int(os.environ['LOOKBACK_MINUTES'])

# Time interval between each consequent alerts (e.g., %5 change continues for 60 secs but the alert should be sent once instead of 30 repetitions.)
# Send the alert every <ALERT_REPEAT_CYCLE_FREQ> sencods.
ALERT_REPEAT_CYCLE_FREQ = int(os.environ['ALERT_REPEAT_CYCLE_FREQ'])

class CryptoMonitor:
    
    def __init__(self, symbols):
        self.SlackAgentInstance = SlackAgent()
        self.slack_channel = "coingecko"
        self.is_deleted = False
        self.symbol_ids = ",".join(symbols)
        self.THRESHOLD = THRESHOLD
        self.alert_repeat_cycle_sec = round(ALERT_REPEAT_CYCLE_FREQ / 3)

        self.loop_time_sleep = 3
        self.rolling_window = int(LOOKBACK_MINUTES * (60 / self.loop_time_sleep))
        self.total_row_limit = self.rolling_window * 2
        self.used_columns = ["symbol", "current_price", "date", "price_change_percentage_1h_in_currency", "total_volume", "is_checked"]
        self.url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={self.symbol_ids}&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=1h"
        self.df_main = pd.DataFrame()
        
    def _check_data_size(self):
        size = self.df_main.shape[0]
        return size >= self.total_row_limit
    
    def _remove_first_row(self):
        self.df_main.drop(index=self.df_main.iloc[0].name, inplace=True)

    def get_data(self):
        response = requests.request("GET", self.url)
        if response.status_code == 200:
            return response.json()
        else:
            print(response.json())
            quit()

    def process_data(self, response):
        df = pd.DataFrame(response)
        df["date"] = datetime.datetime.now()
        df["is_checked"] = False
        price = df[self.used_columns].pivot(index="date", columns="symbol")
        price.columns.name = None
        return price

    def concatenate_response(self):
        response = self.get_data()
        price = self.process_data(response)
        self.df_main = pd.concat([self.df_main, price], axis=0)

    def calculate_stats(self):
        mean = self.df_main[["current_price"]].rolling(self.rolling_window).mean().shift()
        mean.columns = pd.MultiIndex.from_product([["mean"], self.df_main["current_price"]])
        df_stats = pd.concat([self.df_main, mean], axis=1)
        pct_change = df_stats.apply(lambda x: (x["current_price"] - x["mean"]).abs() / x["mean"] * 100, axis=1)
        pct_change.columns = pd.MultiIndex.from_product([["pct_change"], self.df_main["current_price"]])
        df_stats = pd.concat([df_stats, pct_change], axis=1)
        df_stats["pct_change"] = df_stats["pct_change"].round(decimals=5)
        return df_stats

    def filter_anomalies(self, df_stats):
        df_stats
        last_min = df_stats.iloc[-1, :]["pct_change"].abs()
        now_date = self.df_main.iloc[-1].name
        last_min_stats = last_min.loc[(last_min > self.THRESHOLD) & (df_stats.rolling(self.alert_repeat_cycle_sec).is_checked.max().iloc[-1, :] == 0)]
        if last_min_stats.shape[0] > 0:
            print(last_min_stats.tail())
            self.df_main.loc[now_date, ("is_checked", last_min_stats.index)] = True
            print(" - " * 10)           
            last_min_stats.index.name = None
            last_min_stats.index = last_min_stats.index.str.upper()
            entry_edit = last_min_stats.to_string()
            self.SlackAgentInstance.send_alert(text=entry_edit, channel=self.slack_channel)

    def start_monitor(self):
        print("start df: ", self.df_main)
        while True:
            if self._check_data_size():
                self._remove_first_row()
            self.concatenate_response()
            df_stats = self.calculate_stats()
            if df_stats.shape[0] > 0:
                self.filter_anomalies(df_stats)
            print(df_stats[["pct_change", "is_checked"]])

            if datetime.datetime.now().strftime("%H:%M") == "00:00" and not self.is_deleted:
                self.SlackAgentInstance.delete_messages(channel=self.slack_channel)
                self.is_deleted = True

            elif datetime.datetime.now().strftime("%H:%M") == "00:01":
                self.is_deleted = False
                sleep(self.loop_time_sleep)

            else:
                sleep(self.loop_time_sleep)

if __name__ == "__main__":
    monitor_instance = CryptoMonitor(SYMBOLS)
    monitor_instance.start_monitor()
    

    