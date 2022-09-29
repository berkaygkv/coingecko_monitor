import requests
import pandas as pd
import datetime
from time import sleep
import os
from slack_api import SlackAgent
import csv

pd.options.display.max_columns = None

# Temporal CSV file
TEMPORAL_FILE_NAME = "temporal_file.csv"

# CoinGecko asset ids that will be monitored by the script
SYMBOLS = os.environ["SYMBOLS"].split(",")

# Threshold value after which an alert message will be sent
THRESHOLD = float(os.environ["THRESHOLD"])

# Number of minutes that the script will take into account for Moving Averaging process
LOOKBACK_MINUTES = int(os.environ["LOOKBACK_MINUTES"])

# Time interval between each consequent alerts (e.g., %5 change continues for 60 secs but the alert should be sent once instead of 30 repetitions.)
# Send the alert every <ALERT_REPEAT_CYCLE_FREQ> sencods.
ALERT_REPEAT_CYCLE_FREQ = int(os.environ["ALERT_REPEAT_CYCLE_FREQ"])


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
        self.used_columns = [
            "symbol",
            "current_price",
            "date",
            "price_change_percentage_1h_in_currency",
            "total_volume",
            "is_checked_last_min",
            "is_checked_last_hour"
        ]
        self.url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={self.symbol_ids}&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=1h"
        self.df_main = pd.DataFrame()

    def _check_data_size(self):
        size = self.df_main.shape[0]
        return size >= self.total_row_limit

    def _create_temporal_csv_file(self, df):
        df.columns.name = None
        df.reset_index(inplace=True)
        df.to_csv(TEMPORAL_FILE_NAME, index=False)
        print("CSV Created.")

    def _append_csv(self, df):
        df.columns.name = None
        df.reset_index(inplace=True)
        df.to_csv(TEMPORAL_FILE_NAME, mode="a", header=False, index=False)

    def _remove_first_row(self,):
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
        df["is_checked_last_min"] = False
        df["is_checked_last_hour"] = False
        price = df[self.used_columns].pivot(index="date", columns="symbol")
        price.columns.name = None
        return price

    def concatenate_response(self):
        response = self.get_data()
        price = self.process_data(response)
        self.df_main = pd.concat([self.df_main, price], axis=0)

    def calculate_stats(self):
        mean = (
            self.df_main[["current_price"]].rolling(self.rolling_window).mean().shift()
        )
        mean.columns = pd.MultiIndex.from_product(
            [["mean"], self.df_main["current_price"]]
        )
        df_stats = pd.concat([self.df_main, mean], axis=1)
        pct_change = df_stats.apply(
            lambda x: (x["current_price"] - x["mean"]).abs() / x["mean"] * 100, axis=1
        )
        pct_change.columns = pd.MultiIndex.from_product(
            [["pct_change"], self.df_main["current_price"]]
        )
        df_stats = pd.concat([df_stats, pct_change], axis=1)
        df_stats["pct_change"] = df_stats["pct_change"].round(decimals=5)
        return df_stats

    def filter_anomalies(self, df_stats):
        last_min = df_stats.iloc[-1, :]["pct_change"]
        now_date = self.df_main.iloc[-1].name
        last_min_stats = last_min.loc[
            (last_min.abs() > self.THRESHOLD)
            & (
                df_stats.rolling(self.alert_repeat_cycle_sec)
                .is_checked_last_min.max()
                .iloc[-1, :]
                == 0
            )
        ]

        last_hour = df_stats.iloc[-1, :]["price_change_percentage_1h_in_currency"]
        last_hour_stats = last_hour.loc[
            (last_hour.abs() > self.THRESHOLD)
            & (
                df_stats.rolling(10 * 2 * 60)
                .is_checked_last_hour.max()
                .iloc[-1, :]
                == 0
            )
        ]

        if last_min_stats.shape[0] > 0:
            print(last_min_stats.tail())
            last_min_stats = last_min_stats.map(lambda x: f"%{round(abs(x), 1)} düştü:arrow_down:" if max(0, x) == 0 else f"%{round(abs(x), 1)} arttı:arrow_up:")
            self.df_main.loc[now_date, ("is_checked_last_min", last_min_stats.index)] = True
            print(" - " * 10)
            last_min_stats.index.name = None
            last_min_stats.index = last_min_stats.index.str.upper()
            entry_edit = "*SON 5 DAKİKADA*\n" + last_min_stats.to_string() + "\n" + "@berkaygokova"
            self.SlackAgentInstance.send_alert(
                text=entry_edit, channel=self.slack_channel
            )

        elif last_hour_stats.shape[0] > 0:
            print(last_hour_stats.tail())
            last_hour_stats = last_hour_stats.map(lambda x: f"%{round(abs(x), 1)} düştü :arrow_down:" if max(0, x) == 0 else f"%{round(abs(x), 1)} arttı :arrow_up:")
            self.df_main.loc[now_date, ("is_checked_last_hour", last_hour_stats.index)] = True
            print(" - " * 10)
            last_hour_stats.index.name = None
            last_hour_stats.index = last_hour_stats.index.str.upper()
            entry_edit = "*SON 1 SAATTE*\n" + last_hour_stats.to_string() + "\n" + "@berkaygokova"
            self.SlackAgentInstance.send_alert(
                text=entry_edit, channel=self.slack_channel
            )

            

    def start_monitor(self):
        print("start df: ", self.df_main)
        is_start = True
        while True:
            if self._check_data_size():
                self._remove_first_row()
            self.concatenate_response()
            df_stats = self.calculate_stats()
            if df_stats.shape[0] > 0:
                self.filter_anomalies(df_stats)
            print(self.df_main.iloc[-1].name.strftime("%m-%d %H:%M:%S"))

            if is_start:
                self._create_temporal_csv_file(df_stats)
                is_start = False
            elif not is_start:
                self._append_csv(df_stats.iloc[-1:, :])
                
            if (
                datetime.datetime.now().strftime("%H:%M") == "00:00"
                and not self.is_deleted
            ):
                self.SlackAgentInstance.delete_messages(channel=self.slack_channel)
                self.is_deleted = True
                is_start = True

            elif datetime.datetime.now().strftime("%H:%M") == "00:01":
                self.is_deleted = False
                sleep(self.loop_time_sleep)

            else:
                sleep(self.loop_time_sleep)


if __name__ == "__main__":
    monitor_instance = CryptoMonitor(SYMBOLS)
    monitor_instance.start_monitor()
