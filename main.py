from func import run_bot
from func import check_trade
import threading


thread = threading.Thread(target=check_trade)
thread.start()

run_bot()






