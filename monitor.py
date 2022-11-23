import pandas as pd
import os
from monitor_app import SeleniumMonitor
from monitor_app import *
import jmespath
os.environ["no_proxy"]="*"


pd.options.display.max_columns = None

# Temporal CSV file
TEMPORAL_FILE_NAME = "temporal_file.csv"

# CoinGecko asset ids that will be monitored by the script ("id" field must be provided)
SYMBOLS = os.environ["SYMBOLS"].split(",")

# Threshold value after which an alert message will be sent
THRESHOLD = float(os.environ["THRESHOLD"])

# Number of minutes that the script will take into account for Moving Averaging process
LOOKBACK_MINUTES = int(os.environ["LOOKBACK_MINUTES"])

# Time interval between each consequent alerts (e.g., %5 change continues for 60 secs but the alert should be sent once instead of 30 repetitions.)
# Send the alert every <ALERT_REPEAT_CYCLE_FREQ> sencods.
ALERT_REPEAT_CYCLE_FREQ = int(os.environ["ALERT_REPEAT_CYCLE_FREQ"])

# chromedriver.exe path
CHROME_EXE_PATH = os.environ["CHROME_EXE_PATH"]

def run_monitor():
    try:
        monitor_obj = SeleniumMonitor(threshold=THRESHOLD, executable_path=CHROME_EXE_PATH)
        monitor_obj.start_monitoring()
    except Exception as exc:
        monitor_obj.terminate_session()
        raise exc


if __name__ == "__main__":
    monitor = RequestMonitor()
    monitor.run_request_monitoring()
