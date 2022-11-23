import json
import time

import jmespath
import pandas as pd
import requests

from .exceptions import PostRequestFail
from .utils import *


class RequestMonitor():
    def __init__(self) -> None:
        Logger.configure()
        Logger.logger.info("INITIAL RUN.")

    def process_pairs_data(self):
        pairs_data = self.get_pairs_json()
        data = jmespath.search("[*].{name: d[2], price: d[3], change_1h: d[4], change_5min: d[5]}", pairs_data["data"])
        df = pd.DataFrame(data).set_index("name")
        df.index.name = None
        return df


    def get_pairs_json(self):
        url = Configs.scan_url
        payload = json.dumps(Configs.request_parameters["payload"])
        headers = Configs.request_parameters["headers"]
        response = requests.request("POST", url, headers=headers, data=payload, timeout=30)
        if response.status_code == 200:
            return response.json()

        else:
            raise PostRequestFail


    def run_request_monitoring(self):
        is_instance_started = True
        while True:
            try:
                pairs_data = self.get_pairs_json()
                data = jmespath.search("[*].{name: d[2], price: d[3], change_1h: d[4], change_5min: d[5]}", pairs_data["data"])
                df = pd.DataFrame(data).set_index("name")
                if is_instance_started:
                    df_timing = df.copy()
                    df_timing["5min_cooldown"] = Configs.minute_cooldown
                    df_timing["1h_cooldown"] = Configs.hourly_cooldown
                    df_timing = df_timing[["5min_cooldown", "1h_cooldown"]]
                    is_instance_started = False

                df.index.name = None
                now = datetime.datetime.now(tz=pytz.UTC).astimezone(Configs.timezone)
                if not (now > now.replace(second=0, hour=1, minute=20) and now < now.replace(second=0, hour=6, minute=0)):
                    latest_threshold = Configs.THRESHOLD

                else:
                    latest_threshold = Configs.THRESHOLD + 5
                print("Current threshold: ", latest_threshold)
                Logger.logger.info("Current threshold: " + str(latest_threshold) + "\n" + df.to_string())
                df_timing = UtilsManager.calculate_stats(df, df_timing, threshold=latest_threshold, enable_notification=True)
            except Exception as exc:
                Logger.logger.error(exc)
            time.sleep(15)
