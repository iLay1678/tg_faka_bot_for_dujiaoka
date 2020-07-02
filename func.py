import threading
import telegram
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from config import TOKEN,PAY_TYPE,PAY_TIMEOUT,DB_HOST,DB_PORT,DB_DATABASE,DB_USERNAME,DB_PASSWORD,NAME, ADMIN_ID, ADMIN_COMMAND_START, ADMIN_COMMAND_QUIT
import pymysql.cursors
import sqlite3
import time
import datetime
import random
import os
import html2text
import urllib.parse
from epay import make_data_dict, epay_submit, check_status

ROUTE, CATEGORY, PRICE, SUBMIT, TRADE = range(5)
ADMIN_TRADE_ROUTE, ADMIN_TRADE_EXEC, CATEGORY_FUNC_EXEC = range(3)
bot = telegram.Bot(token=TOKEN)


def run_bot():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
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
        },
        conversation_timeout=20,
        fallbacks=[CommandHandler('{}'.format(ADMIN_COMMAND_QUIT), icancel)]
    )
    
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
                CallbackQueryHandler(pay_way, pattern='^' + str('提交订单') + '$'),
                CallbackQueryHandler(submit_trade, pattern='^' + '(支付宝|微信|QQ钱包)' + '$'),
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
    dispatcher.add_handler(admin_handler)
    
    updater.start_polling()
    updater.idle()



def get_trade_id():
    now_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    random_num = random.randint(0, 99)
    if random_num <= 10:
        random_num = str(0) + str(random_num)
    unique_num = str(now_time) + str(random_num)
    return unique_num

# -----------------------管理员函数区域-------------------------------
# -----------------------管理员函数区域-------------------------------
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
                    '描述：*{}*\n'.format(trade_id, status, username, card_context, description),
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
                '描述：*{}*\n'
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

# -----------------------用户函数区域-------------------------------
# -----------------------用户函数区域-------------------------------


def start(update, context):
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
    cursor.execute("select * from products where pd_class=%s and pd_status=%s ORDER BY ord desc",
                   (category_name, '1'))
    goods = cursor.fetchall()
    for i in goods:
        goods_id = i['id']
        goods_list = [InlineKeyboardButton(i['pd_name'] + ' | 价格:{} | 库存:{} '.format(i['actual_price'],i['in_stock']),
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
    in_stock = goods['in_stock']
    pd_type = goods['pd_type']
    conn.close()
    if pd_type == 1 :
        goods_type = '自动发货'
    else:
        goods_type = '手动发货'
    if in_stock == 0 :
        query.edit_message_text(text="该商品暂时*无库存*，等待补货\n"
                                     "会话已结束，使用 /start 重新发起会话",
                                parse_mode='Markdown', )
        return ConversationHandler.END
    elif in_stock > 0:
        goods_name=goods['pd_name']
        price = goods['actual_price']
        descrip = html2text.html2text(goods['pd_info'])
        context.user_data['goods_id'] = goods_id
        context.user_data['goods_name'] = goods_name
        context.user_data['goods_type'] = goods_type
        context.user_data['price'] = price
        keyboard = [
            [InlineKeyboardButton("提交订单", callback_data=str('提交订单')),
             InlineKeyboardButton("下次一定", callback_data=str('下次一定'))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            text="商品名：*{}*\n"
                 "价格：*{}*\n"
                 "发货方式：*{}*\n"
                 "介绍：*{}*\n".format(goods_name, price,goods_type, descrip),
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return SUBMIT

def pay_way(update, context):
    query = update.callback_query
    query.answer()
    keyboard=[]
    keyboards = [
        keyboard
        ]
    for i in PAY_TYPE:
        keyboard.append(InlineKeyboardButton(i, callback_data=str(i)))
    reply_markup = InlineKeyboardMarkup(keyboards)
    query.edit_message_text(
            text="请选择支付方式：",
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
    pay_name = update.callback_query.data
    if pay_name == '支付宝':
        paytype = 'alipay'
    elif pay_name == '微信':
        paytype = 'wxpay'
    elif pay_name == 'QQ钱包':
        paytype = 'qqpay'
    try:
        conn = sqlite3.connect('faka.sqlite3')
        cursor = conn.cursor()
        cursor.execute("select * from trade where user_id=? and status=?", (user_id, 'unpaid'))
        trade_list = cursor.fetchone()
        conn.close()
        if trade_list is None:
            goods_name = context.user_data['goods_name']
            goods_id = context.user_data['goods_id']
            goods_type = context.user_data['goods_type']
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
            card_id = 'no'
            if goods_type == '自动发货':
                card_content = 'auto'
            else:
                card_content = 'no'
            cursor.execute("update products set in_stock=in_stock-1 where id=%s", (goods_id,))
            conn.commit()
            cursor.close()
            conn.close()
            now_time = int(time.time())
            trade_data = make_data_dict(price, name, trade_id, paytype)
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
                query.edit_message_text(
                   text = "请使用{}扫一扫支付，务必在{}s内支付完成，超时支付会导致发货失败！[​​​​​​​​​​​](https://api.961678.xyz/qrcode/{}".format(pay_name,PAY_TIMEOUT,urllib.parse.quote(pay_url,safe="")),
                    parse_mode='Markdown'
                    )
                return ConversationHandler.END
            else :
                keyboard = [
                    [InlineKeyboardButton("支付宝", callback_data=str('支付宝')),
                    InlineKeyboardButton("微信", callback_data=str('微信')),
                    InlineKeyboardButton("QQ钱包", callback_data=str('QQ钱包'))
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                query.edit_message_text(text='当前支付方式维护，请选择其他支付方式',reply_markup=reply_markup)
                return SUBMIT
        else:
            query.edit_message_text('您存在未支付订单，请支付或等待订单过期后重试！')
            return ConversationHandler.END
    except Exception as e:
        print(e)


def cancel_trade(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(text='记得哦～下次一定 \n\n'
                                 '主菜单: /start')
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
        update.message.reply_text('订单号有误，请确认后输入\n\n'
                                  '主菜单: /start')
        return ConversationHandler.END
    elif trade_list[10] == 'locking':
        goods_name = trade_list[2]
        description = trade_list[3]
        trade_id = trade_list[0]
        update.message.reply_text(
            '*订单查询成功*!\n'
            '订单号：`{}`\n'
            '订单状态：*已取消*\n'
            '原因：*逾期未付*\n\n'
            '主菜单: /start'
            .format(trade_id),
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
            '卡密内容：`{}`\n\n'
            '主菜单: /start'.format(trade_id, goods_name, description, card_context),
            parse_mode='Markdown',
        )
        return ConversationHandler.END
    elif trade_list[10] == 'locking':
        trade_id = trade_list[0]
        goods_name = trade_list[2]
        description = trade_list[3]
        use_way = trade_list[4]
        card_context = trade_list[6]
        update.message.reply_text(
            '*订单查询成功*!\n'
            '订单号：`{}`\n'
            '订单状态：*已取消*\n'
            '原因：*逾期未付*\n\n'
            '主菜单: /start'
            .format(trade_id),
            parse_mode='Markdown',
        )
        return ConversationHandler.END
    elif trade_list[10] == 'unpaid':
        trade_id = trade_list[0]
        goods_name = trade_list[2]
        description = trade_list[3]
        use_way = trade_list[4]
        card_context = trade_list[6]
        update.message.reply_text(
            '*订单查询成功*!\n'
            '订单号：`{}`\n'
            '订单状态：*待支付*\n'
            '主菜单: /start'
            .format(trade_id),
            parse_mode='Markdown',
        )
        return ConversationHandler.END
    else :
        update.message.reply_text(
            '订单不存在!\n',
            parse_mode='Markdown',
        )
        return ConversationHandler.END
def cancel(update, context):
    update.message.reply_text('期待再次见到你～ \n\n'
                              '主菜单: /start')
    return ConversationHandler.END


def check_trade():
    while True:
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
            username = i[8]
            creat_time = i[9]
            goods_name = i[2]
            description = i[3]
            use_way = i[4]
            card_content = i[6]
            sub_time = now_time - int(creat_time)
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
                        if card_content == 'auto' :
                             conn = pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USERNAME,password=DB_PASSWORD,db=DB_DATABASE,cursorclass=pymysql.cursors.DictCursor)
                             cursor = conn.cursor()
                             cursor.execute("select * from cards where product_id=%s and card_status=%s", (goods_id, '1'))
                             card=cursor.fetchone()
                             card_context = card['card_info']
                             card_id=card['id']
                             cursor.execute("update cards set card_status=%s where id=%s", ('2', card_id,))
                             cursor.execute("update cards set updated_at=%s where id=%s", (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), card_id,))
                             conn.commit()
                             conn.close()  
                        else:
                            card_context = '请等待管理员手动发货，发货后您会收到消息推送'
                            card_id='no'
                            bot.send_message(
                            chat_id=ADMIN_ID[0],
                            text='新订单等待处理\n'
                                 '订单号：`{}`\n'
                                 '下单用户：@{}\n'
                                 '商品：*{}*\n\n'
                                 '请及时处理'.format(trade_id, username,goods_name),
                                parse_mode='Markdown',
                            )
                        conn = sqlite3.connect('faka.sqlite3')
                        cursor = conn.cursor()
                        cursor.execute("update trade set status=? where trade_id=?", ('paid', trade_id,))
                        cursor.execute("update trade set card_contents=? where trade_id=?", (card_context, trade_id,))
                        cursor.execute("update trade set card_id=? where trade_id=?", (card_id, trade_id,))
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
        time.sleep(10)

