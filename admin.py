import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from telegram.ext import CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from config import TOKEN,PAY_TIMEOUT,DB_HOST,DB_PORT,DB_DATABASE,DB_USERNAME,DB_PASSWORD,NOTICE, ADMIN_ID, ADMIN_COMMAND_START, ADMIN_COMMAND_QUIT
import sqlite3
import time
import os

ADMIN_TRADE_ROUTE, ADMIN_TRADE_EXEC, CATEGORY_FUNC_EXEC = range(3)
bot = telegram.Bot(token=TOKEN)


def admin(update, context):
    if is_admin(update, context):
        keyboard = [
            [
                InlineKeyboardButton("查询订单", callback_data=str('查询订单')),
                InlineKeyboardButton("重新激活订单", callback_data=str('重新激活订单')),
            ],
            [
                InlineKeyboardButton("手动发货及补发", callback_data=str('手动发货')),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            '请选择指令：',
            reply_markup=reply_markup
        )
        return ADMIN_TRADE_ROUTE
def trade_func_route(update, context):
    query = update.callback_query
    query.answer()
    if update.callback_query.data == '查询订单':
        context.user_data['func'] = '查询订单'
        query.edit_message_text(text="请回复您需要查询的订单号：")
        return ADMIN_TRADE_EXEC
    elif update.callback_query.data == '重新激活订单':
        context.user_data['func'] = '重新激活订单'
        query.edit_message_text(text="请回复您需要重新激活的订单号：")
        return ADMIN_TRADE_EXEC
    elif update.callback_query.data == '手动发货':
        context.user_data['func'] = '手动发货'
        query.edit_message_text(text="请回复 `订单号===发货内容`",parse_mode='Markdown',)
        return ADMIN_TRADE_EXEC

def admin_trade_func_exec(update, context):
    try:
        trade_id = update.message.text
        func = context.user_data['func']
        if func == '查询订单':
            conn = sqlite3.connect('faka.sqlite3')
            cursor = conn.cursor()
            cursor.execute('select * from trade where trade_id=?', (trade_id,))
            trade_list = cursor.fetchone()
            if trade_list is None:
                update.message.reply_text('订单号有误，请确认后输入！')
                return ConversationHandler.END
            else:
                if trade_list[10] == 'paid':
                    status = '已支付'
                elif trade_list[10] == 'locking':
                    status = '已锁定'
                elif trade_list[10] == 'unpaid':
                    status = '未支付'
                goods_name = trade_list[2]
                description = trade_list[3]
                username = trade_list[8]
                card_context = trade_list[6]
                trade_id = trade_list[0]
                update.message.reply_text(
                    '*订单查询成功*!\n'
                    '订单号：`{}`\n'
                    '订单状态：{}\n'
                    '下单用户：@{}\n'
                    '卡密内容：`{}`\n'
                    '介绍：\n{}\n'.format(trade_id, status, username, card_context, description),
                    parse_mode='Markdown',
                )
                return ConversationHandler.END
        elif func == '重新激活订单':
            now_time = int(time.time())
            conn = sqlite3.connect('faka.sqlite3')
            cursor = conn.cursor()
            cursor.execute("select * from trade where trade_id=?", (trade_id,))
            trade = cursor.fetchone()
            status = trade[10]
            goods_id = trade[1]
            if status=='paid':
                update.message.reply_text('该订单已支付，无法重新激活')
                return ConversationHandler.END
            else:
                cursor.execute('update trade set creat_time=? where trade_id=?', (now_time, trade_id,))
                cursor.execute('update trade set status=? where trade_id=?', ('unpaid', trade_id,))
                conn.commit()
                conn.close()
                conn = pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USERNAME,password=DB_PASSWORD,db=DB_DATABASE,cursorclass=pymysql.cursors.DictCursor)
                cursor = conn.cursor()
                cursor.execute("update products set in_stock=in_stock-1 where id=%s", (goods_id,))
                conn.commit()
                cursor.close()
                conn.close()
                update.message.reply_text('该订单已经被重新激活，请用户在{}内支付'.format(PAY_TIMEOUT))
                return ConversationHandler.END
        elif func == '手动发货':
            text=trade_id;
            trade_id=text.split('===')[0]
            content=text.split('===')[1]
            conn = sqlite3.connect('faka.sqlite3')
            cursor = conn.cursor()
            cursor.execute('select * from trade where trade_id=?', (trade_id,))
            trade_list = cursor.fetchone()
            goods_name = trade_list[2]
            description = trade_list[3]
            user_id = trade_list[7]
            username = trade_list[8]
            cursor.execute('update trade set card_contents=? where trade_id=?', (content, trade_id,))
            cursor.execute('update trade set status=? where trade_id=?', ('paid', trade_id,))
            conn.commit()
            conn.close()
            bot.send_message(
                            chat_id=ADMIN_ID[0],
                            text='发货成功\n'
                                 '订单号：`{}`\n'
                                 '下单用户：@{}\n'
                                 '商品：*{}*\n'
                                 '卡密内容：`{}`\n'.format(trade_id, username,goods_name,content),
                                parse_mode='Markdown',
                            )
            bot.send_message(
            chat_id=user_id,
            text='您购买的商品已发货!\n'
                '订单号：`{}`\n'
                '商品：*{}*\n'
                '介绍：\n{}\n'
                '卡密内容：`{}`\n'.format(trade_id, goods_name, description, content),
                parse_mode='Markdown',
            )
            return ConversationHandler.END
    except Exception as e:
        print(e)


def is_admin(update, context):
    if update.message.from_user.id in ADMIN_ID:
        return True
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='*非管理员，无权操作*',
            parse_mode='Markdown'
        )
        return False
def icancel(update, context):
    update.message.reply_text('期待再次见到你～ /{}'.format(ADMIN_COMMAND_START))
    return ConversationHandler.END

def itimeout(update, context):
    update.message.reply_text('会话超时，期待再次见到你～ \n\n'
                              '主菜单: /{}'.format(ADMIN_COMMAND_START))
    return ConversationHandler.END



admin_handler = ConversationHandler(
        entry_points=[CommandHandler(ADMIN_COMMAND_START, admin)],

        states={
            ADMIN_TRADE_ROUTE: [
                CommandHandler('{}'.format(ADMIN_COMMAND_QUIT), icancel),
                CallbackQueryHandler(trade_func_route, pattern='^' + '(查询订单|重新激活订单|手动发货)' + '$'),
            ],
            ADMIN_TRADE_EXEC: [
                CommandHandler('{}'.format(ADMIN_COMMAND_QUIT), icancel),
                MessageHandler(Filters.text, admin_trade_func_exec)
            ],
            ConversationHandler.TIMEOUT: [MessageHandler(Filters.all, itimeout)],
        },
        conversation_timeout=300,
        fallbacks=[CommandHandler(ADMIN_COMMAND_QUIT, icancel)]
    )


