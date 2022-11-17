import slack
import os
from pathlib import Path
from time import sleep
import jmespath

from dotenv import load_dotenv
load_dotenv()

# Slack Bot Token
BOT_TOKEN = os.environ['BOT_TOKEN']

# Slack User Token
USER_TOKEN = os.environ['USER_TOKEN']


class BotAgent(slack.WebClient):
    def __init__(self) -> None:
        super().__init__(token=BOT_TOKEN)


class UserAgent(slack.WebClient):
    def __init__(self) -> None:
        super().__init__(token=USER_TOKEN)


class SlackAgent(BotAgent, UserAgent):
    def __init__(self) -> None:
        BotAgent().__init__()
        UserAgent().__init__()

    def send_alert(self, text, channel):
        _ = BotAgent().chat_postMessage(channel='#'+channel, text=text, link_names=1)

    def list_channels(self):
        conversations_data = BotAgent().conversations_list().data
        return dict(jmespath.search("[*].[@.name, @.id]", conversations_data["channels"]))

    def delete_messages(self, channel):
        channel_id = self.list_channels().get(channel)
        if channel_id:
            message_data = UserAgent().conversations_history(channel=channel_id).data
            active_messages = message_data['messages']
            timestamp_list = [m['ts'] for m in active_messages]
            number_of_deleted_messages = 0
            for i in timestamp_list:
                try:
                    UserAgent().chat_delete(channel=channel_id, ts=i)
                    number_of_deleted_messages += 1
                except Exception as esc:
                    print(esc)
                    pass
                sleep(0.2)
            print(number_of_deleted_messages, " messages deleted.")

        else:
            raise TypeError("Channel not found.")


if __name__ == "__main__":
    Agent = SlackAgent()
    #Agent.send_alert(text="deneme2", channel="upwork")
    Agent.delete_messages("upwork")
