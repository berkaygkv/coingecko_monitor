import datetime
from dataclasses import dataclass
import json

import pytz

from .slack_api import SlackAgent


@dataclass
class Configs:
    THRESHOLD = 1
    scan_url = "https://scanner.tradingview.com/crypto/scan"
    js_file = open("request_parameters.json", "r")
    request_parameters = json.load(js_file)
    instance_started = True
    is_deleted = False
    SlackAgentInstance = SlackAgent()
    slack_channel = "coingecko"
    timezone = pytz.timezone("Europe/Istanbul")
    minute_cooldown = datetime.datetime.now(tz=pytz.UTC).astimezone(
        timezone
    ) - datetime.timedelta(minutes=6)
    hourly_cooldown = datetime.datetime.now(tz=pytz.UTC).astimezone(
        timezone
    ) - datetime.timedelta(hours=1, minutes=1)


class UtilsManager(Configs):

    @staticmethod
    def calculate_stats(df, df_timing, threshold):
        now = datetime.datetime.now(tz=pytz.UTC).astimezone(Configs.timezone)
        print(now)
        print(df)
        if not (
            now > now.replace(second=0, hour=1, minute=30)
            and now < now.replace(second=0, hour=1, minute=31)
        ):
            last_5_min = df.loc[df["change_5min"].abs() > threshold, "change_5min"]
            last_1_hour = df.loc[df["change_1h"].abs() > threshold, "change_1h"]
            df_timing_5_min = last_5_min.to_frame().merge(
                df_timing[["5min_cooldown"]],
                left_index=True,
                right_index=True,
                how="left",
            )
            df_timing_1_hour = last_1_hour.to_frame().merge(
                df_timing[["1h_cooldown"]],
                left_index=True,
                right_index=True,
                how="left",
            )

            df_timing_5_min["5min_cooldown"] = (
                now - df_timing_5_min["5min_cooldown"]
            ).dt.total_seconds()
            df_timing_5_min["5min_cooldown"] = (
                df_timing_5_min["5min_cooldown"] >= (60 * 5) + 15
            )

            df_timing_1_hour["1h_cooldown"] = (
                now - df_timing_1_hour["1h_cooldown"]
            ).dt.total_seconds()
            df_timing_1_hour["1h_cooldown"] = (
                df_timing_1_hour["1h_cooldown"] >= (60 * 60) + 15
            )

            last_5_min_table = df_timing_5_min.loc[
                (df_timing_5_min["change_5min"].abs() > threshold)
                & (df_timing_5_min["5min_cooldown"])
            ]
            last_1_hour_table = df_timing_1_hour.loc[
                (df_timing_1_hour["change_1h"].abs() > threshold)
                & (df_timing_1_hour["1h_cooldown"])
            ]

            if last_5_min_table.shape[0] > 0:
                last_5_min_table = last_5_min_table["change_5min"].map(
                    lambda x: f"%{round(abs(x), 1)} düştü:arrow_down:"
                    if max(0, x) == 0
                    else f"%{round(abs(x), 1)} arttı:arrow_up:"
                )
                entry_edit = (
                    ":right_anger_bubble:*SON 5 DAKİKADA*\n"
                    + last_5_min_table.to_string()
                    + "\n"
                    + " - " * 15
                )
                new_minute_cooldown = datetime.datetime.now(tz=pytz.UTC).astimezone(
                    Configs.timezone
                )
                new_hourly_cooldown = datetime.datetime.now(tz=pytz.UTC).astimezone(
                    Configs.timezone
                )
                df_timing.loc[
                    last_5_min_table.index, "5min_cooldown"
                ] = new_minute_cooldown
                df_timing.loc[
                    last_5_min_table.index, "1h_cooldown"
                ] = new_hourly_cooldown
                print(entry_edit)
                # Configs.SlackAgentInstance.send_alert(
                #     text=entry_edit, channel=Configs.slack_channel
                # )

            elif last_1_hour_table.shape[0] > 0:
                last_1_hour_table = last_1_hour_table["change_1h"].map(
                    lambda x: f"%{round(abs(x), 1)} düştü:arrow_down:"
                    if max(0, x) == 0
                    else f"%{round(abs(x), 1)} arttı:arrow_up:"
                )
                entry_edit = (
                    ":right_anger_bubble:*SON 1 SAATTE*\n"
                    + last_1_hour_table.to_string()
                    + "\n"
                    + " - " * 15
                )
                new_hourly_cooldown = datetime.datetime.now(tz=pytz.UTC).astimezone(
                    Configs.timezone
                )
                new_minute_cooldown = datetime.datetime.now(tz=pytz.UTC).astimezone(
                    Configs.timezone
                )
                df_timing.loc[
                    last_1_hour_table.index, "1h_cooldown"
                ] = new_hourly_cooldown
                df_timing.loc[
                    last_1_hour_table.index, "5min_cooldown"
                ] = new_minute_cooldown
                print(entry_edit)
                # Configs.SlackAgentInstance.send_alert(
                #     text=entry_edit, channel=Configs.slack_channel
                # )
            Configs.is_deleted = False

        elif not Configs.is_deleted:
            Configs.SlackAgentInstance.delete_messages(channel=Configs.slack_channel)
            Configs.is_deleted = True

        else:
            pass
        
        return df_timing