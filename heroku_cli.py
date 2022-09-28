import subprocess
subprocess.call("heroku ps:copy temporal_file.csv --app cumonitor --dyno=worker.1",shell=False, executable='/opt/homebrew/bin/heroku')