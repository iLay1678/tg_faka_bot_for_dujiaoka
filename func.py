import threading
import telegram
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from config import TOKEN,PAY_TIMEOUT,DB_HOST,DB_PORT,DB_DATABASE,DB_USERNAME,DB_PASSWORD,NAME
import pymysql.cursors
import sqlite3
import time
import datetime
import random
import os
import html2text
from epay import make_data_dict, epay_submit, check_status

ROUTE, CATEGORY, PRICE, SUBMIT, TRADE = range(5)
CATEGORY_FUNC_EXEC  = range(11)
bot = telegram.Bot(token=TOKEN)


def run_bot():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    start_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],

        states={
            ROUTE: [
                CallbackQueryHandler(category_filter, pattern='^' + str('购买商品') + '$'),
                CallbackQueryHandler(trade_filter, pattern='^' + str('查询订单') + '$'),
            ],
            CATEGORY: [
                CallbackQueryHandler(goods_filter, pattern='.*?'),
            ],
            PRICE: [
                CallbackQueryHandler(user_price_filter, pattern='.*?'),
            ],
            SUBMIT: [
                CallbackQueryHandler(submit_trade, pattern='^' + str('提交订单') + '$'),
                CallbackQueryHandler(cancel_trade, pattern='^' + str('下次一定') + '$')
            ],
            TRADE: [
                MessageHandler(Filters.text, trade_query)
            ],
        },
        conversation_timeout=20,
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(start_handler)

    updater.start_polling()
    updater.idle()



def get_trade_id():
    now_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    random_num = random.randint(0, 99)
    if random_num <= 10:
        random_num = str(0) + str(random_num)
    unique_num = str(now_time) + str(random_num)
    return unique_num


def icancel(update, context):
    update.message.reply_text('期待再次见到你～ /{}'.format(ADMIN_COMMAND_START))
    return ConversationHandler.END


# -----------------------用户函数区域-------------------------------
# -----------------------用户函数区域-------------------------------


def start(update, context):
    print('进入start函数')
    keyboard = [
        [InlineKeyboardButton("购买商品", callback_data=str('购买商品')),
         InlineKeyboardButton("查询订单", callback_data=str('查询订单'))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "欢迎光临{}\n"
        '请选择您的操作：'.format(NAME),
        reply_markup=reply_markup
    )
    return ROUTE


def category_filter(update, context):
    query = update.callback_query
    query.answer()
    keyboard = []
    conn = pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USERNAME,password=DB_PASSWORD,db=DB_DATABASE,cursorclass=pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("select * from classifys where c_status=%s ORDER BY ord desc",( '1'))
    categorys = cursor.fetchall()
    conn.close()
    print(categorys)
    for i in categorys:
        category_list = [InlineKeyboardButton(i['name'], callback_data=str(i['id']))]
        keyboard.append(category_list)
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text="选择分类",
        reply_markup=reply_markup
    )
    return CATEGORY


def goods_filter(update, context):
    query = update.callback_query
    query.answer()
    keyboard = []
    category_name = update.callback_query.data
    context.user_data['category_name'] = category_name
    conn = pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USERNAME,password=DB_PASSWORD,db=DB_DATABASE,cursorclass=pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("select * from products where pd_class=%s and pd_status=%s and pd_type=%sORDER BY ord desc",
                   (category_name, '1','1'))
    goods = cursor.fetchall()
    for i in goods:
        goods_id = i['id']
        cursor.execute("select * from cards where product_id=%s and card_status=%s", (goods_id, '1'))
        active_cards = cursor.fetchall()
        goods_list = [InlineKeyboardButton(i['pd_name'] + ' | 价格:{} | 库存:{} '.format(i['actual_price'],len(active_cards)),
                                           callback_data=str(i['id']))]
        keyboard.append(goods_list)
    conn.close()
    reply_markup = InlineKeyboardMarkup(keyboard)
    if len(goods) == 0:
        query.edit_message_text(text="该分类下暂时还没有商品 主菜单: /start \n")
        return ConversationHandler.END
    else:
        query.edit_message_text(
            text="选择您要购买的商品：\n"
                 "库存：当前可购买数量\n",
            reply_markup=reply_markup)
        return PRICE


def user_price_filter(update, context):
    query = update.callback_query
    query.answer()
    goods_name = update.callback_query.data
    category_name = context.user_data['category_name']
    conn = pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USERNAME,password=DB_PASSWORD,db=DB_DATABASE,cursorclass=pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("select * from products where pd_class=%s and id=%s", (category_name, goods_name,))
    goods = cursor.fetchone()
    goods_id = goods['id']
    cursor.execute("select * from cards where product_id=%s and card_status=%s", (goods_id, '1'))
    active_cards = cursor.fetchall()
    conn.close()
    if len(active_cards) == 0 :
        query.edit_message_text(text="该商品暂时*无库存*，等待补货\n"
                                     "会话已结束，使用 /start 重新发起会话",
                                parse_mode='Markdown', )
        return ConversationHandler.END
    elif len(active_cards) > 0:
        goods_name=goods['pd_name']
        price = goods['actual_price']
        descrip = html2text.html2text(goods['pd_info'])
        context.user_data['goods_id'] = goods_id
        context.user_data['goods_name'] = goods_name
        context.user_data['price'] = price
        keyboard = [
            [InlineKeyboardButton("提交订单", callback_data=str('提交订单')),
             InlineKeyboardButton("下次一定", callback_data=str('下次一定'))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text="商品名：*{}*\n"
                 "价格：*{}*\n"
                 "介绍：*{}*\n".format(goods_name, price, descrip),
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return SUBMIT


def submit_trade(update, context):
    query = update.callback_query
    query.answer()
    user = update.callback_query.message.chat
    user_id = user.id
    username = user.username
    try:
        conn = sqlite3.connect('faka.sqlite3')
        cursor = conn.cursor()
        cursor.execute("select * from trade where user_id=? and status=?", (user_id, 'unpaid'))
        trade_list = cursor.fetchone()
        print(trade_list)
        conn.close()
        if trade_list is None:
            goods_name = context.user_data['goods_name']
            goods_id = context.user_data['goods_id']
            category_name = context.user_data['category_name']
            name = goods_name
            price = context.user_data['price']
            trade_id = get_trade_id()
            conn = pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USERNAME,password=DB_PASSWORD,db=DB_DATABASE,cursorclass=pymysql.cursors.DictCursor)
            cursor = conn.cursor()
            cursor.execute("select * from products where id=%s", (goods_id,))
            goods_info = cursor.fetchone()
            description = html2text.html2text(goods_info['pd_info'])
            use_way = html2text.html2text(goods_info['pd_info'])
            cursor.execute("select * from cards where product_id=%s and card_status=%s", (goods_id, '1'))
            card_info = cursor.fetchone()
            card_id = card_info['id']
            card_content = card_info['card_info']
            cursor.execute("update products set in_stock=in_stock-1 where id=%s", (goods_id,))
            conn.commit()
            cursor.close()
            conn.close()
            now_time = int(time.time())
            trade_data = make_data_dict(price, name, trade_id)
            pay_url = epay_submit(trade_data)
            if pay_url != 'API请求失败':
                print('API请求成功，已成功返回支付链接')
                conn = sqlite3.connect('faka.sqlite3')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO trade VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (trade_id, goods_id, goods_name, description, use_way, card_id,
                                card_content, user_id, username, now_time, 'unpaid',))
                conn.commit()
                conn.close()
                keyboard = [[InlineKeyboardButton("点击跳转支付", url=pay_url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                query.edit_message_text(
                    '请在{}s内支付完成，超时支付会导致发货失败！\n'
                    '[点击这里]({})跳转支付，或者点击下方跳转按钮'.format(PAY_TIMEOUT, pay_url),
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            return ConversationHandler.END
        else:
            query.edit_message_text('您存在未支付订单，请支付或等待订单过期后重试！')
            return ConversationHandler.END
    except Exception as e:
        print(e)


def cancel_trade(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="记得哦～下次一定")
    return ConversationHandler.END


def trade_filter(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="请回复您需要查询的订单号：")
    return TRADE


def trade_query(update, context):
    trade_id = update.message.text
    user = update.message.from_user
    user_id = user.id
    conn = sqlite3.connect('faka.sqlite3')
    cursor = conn.cursor()
    cursor.execute('select * from trade where trade_id=? and user_id=?', (trade_id, user_id,))
    trade_list = cursor.fetchone()
    conn.close()
    if trade_list is None:
        update.message.reply_text('订单号有误，请确认后输入！')
        return ConversationHandler.END
    elif trade_list[10] == 'locking':
        goods_name = trade_list[2]
        description = trade_list[3]
        trade_id = trade_list[0]
        update.message.reply_text(
            '*订单查询成功*!\n'
            '订单号：`{}`\n'
            '订单状态：*已取消*\n'
            '原因：*逾期未付*'.format(trade_id),
            parse_mode='Markdown',
        )
        return ConversationHandler.END
    elif trade_list[10] == 'paid':
        trade_id = trade_list[0]
        goods_name = trade_list[2]
        description = trade_list[3]
        use_way = trade_list[4]
        card_context = trade_list[6]
        update.message.reply_text(
            '*订单查询成功*!\n'
            '订单号：`{}`\n'
            '商品：*{}*\n'
            '描述：*{}*\n'
            '卡密内容：`{}`\n'.format(trade_id, goods_name, description, card_context),
            parse_mode='Markdown',
        )
        return ConversationHandler.END


def cancel(update, context):
    update.message.reply_text('期待再次见到你～')
    return ConversationHandler.END


def check_trade():
    while True:
        print('---------------订单轮询开始---------------')
        conn = sqlite3.connect('faka.sqlite3')
        cursor = conn.cursor()
        cursor.execute("select * from trade where status=?", ('unpaid',))
        unpaid_list = cursor.fetchall()
        conn.close()
        for i in unpaid_list:
            now_time = int(time.time())
            trade_id = i[0]
            goods_id = i[1]
            user_id = i[7]
            creat_time = i[9]
            goods_name = i[2]
            description = i[3]
            use_way = i[4]
            card_context = i[6]
            card_id = i[5]
            sub_time = now_time - int(creat_time)
            print(sub_time)
            if sub_time >= PAY_TIMEOUT:
                conn = sqlite3.connect('faka.sqlite3')
                cursor = conn.cursor()
                cursor.execute("update trade set status=? where trade_id=?", ('locking', trade_id,))
                conn.commit()
                conn.close()
                conn = pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USERNAME,password=DB_PASSWORD,db=DB_DATABASE,cursorclass=pymysql.cursors.DictCursor)
                cursor = conn.cursor()
                cursor.execute("update products set in_stock=in_stock+1 where id=%s", ( goods_id,))
                conn.commit()
                cursor.close()
                conn.close()
                bot.send_message(
                    chat_id=user_id,
                    text='很遗憾，订单已关闭\n'
                         '订单号：`{}`\n'
                         '原因：逾期未付\n'.format(trade_id),
                    parse_mode='Markdown',
                )
            else:
                try:
                    rst = check_status(trade_id)
                    if rst == '支付成功':
                        conn = sqlite3.connect('faka.sqlite3')
                        cursor = conn.cursor()
                        cursor.execute("update trade set status=? where trade_id=?", ('paid', trade_id,))
                        conn.commit()
                        conn.close()
                        conn = pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USERNAME,password=DB_PASSWORD,db=DB_DATABASE,cursorclass=pymysql.cursors.DictCursor)
                        cursor = conn.cursor()
                        cursor.execute("update cards set card_status=%s where id=%s", ('2', card_id,))
                        conn.commit()
                        conn.close()
                        bot.send_message(
                            chat_id=user_id,
                            text='恭喜！订单支付成功!\n'
                                 '订单号：`{}`\n'
                                 '商品：*{}*\n'
                                 '描述：*{}*\n'
                                 '卡密内容：`{}`\n'.format(trade_id, goods_name, description, card_context),
                            parse_mode='Markdown',
                        )
                except Exception as e:
                    print(e)
            time.sleep(3)
        print('---------------订单轮询结束---------------')
        time.sleep(10)


def clear_html_re(src_html):
    content = re.sub(r"</?(.+?)>", "", src_html) # 去除标签
    # content = re.sub(r"&nbsp;", "", content)
    dst_html = re.sub(r"\s+", "", content)  # 去除空白字符
    return dst_html