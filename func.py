from telegram.ext import Updater
from config import TOKEN
from admin import admin_handler
from user import start_handler


def run_bot():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(admin_handler)

    updater.start_polling()
    updater.idle()
