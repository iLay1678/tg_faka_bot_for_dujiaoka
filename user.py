import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from telegram.ext import CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from config import TOKEN,PAY_TIMEOUT,DB_HOST,DB_PORT,DB_DATABASE,DB_USERNAME,DB_PASSWORD,NOTICE,PAYMENT_METHOD,ADMIN_ID
import sqlite3
import time
import datetime
import random
import importlib
import sqlite3
import html2text
import urllib.parse
import pymysql.cursors

ROUTE, CATEGORY, PRICE, SUBMIT, TRADE, CHOOSE_PAYMENT_METHOD = range(6)
bot = telegram.Bot(token=TOKEN)


def start(update, context):
    keyboard = [
        [InlineKeyboardButton("购买商品", callback_data=str('购买商品')),
         InlineKeyboardButton("查询订单", callback_data=str('查询订单'))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "{}\n\n"
        '请选择您的操作：'.format(NOTICE),
        parse_mode='Markdown',
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
                 "介绍：\n{}\n".format(goods_name, price,goods_type, descrip),
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return CHOOSE_PAYMENT_METHOD

def choose_payment_method(update, context):
    query = update.callback_query
    query.answer()
    keyboard = []
    for i in PAYMENT_METHOD:
            for j in PAYMENT_METHOD[i]:
                payment_method_list = [InlineKeyboardButton(PAYMENT_METHOD[i][j], callback_data=str(i)+'.'+str(j))]
                keyboard.append(payment_method_list)
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
            text="请选择您的支付方式：",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )            
    return SUBMIT

def submit_trade(update, context):
    print('进入SUBMIT函数')
    query = update.callback_query
    query.answer()
    user = update.callback_query.message.chat
    user_id = user.id
    if user.username:
        username = user.username
    else:
        username='用户未设置用户名'
    chat_id = update.effective_chat.id
    user_payment_method = update.callback_query.data
    
    print(user_payment_method)
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
            cursor.close()
            conn.close()
            goods_info = cursor.fetchone()
            description = html2text.html2text(goods_info['pd_info'])
            use_way = html2text.html2text(goods_info['pd_info'])
            card_id = 'no'
            if goods_type == '自动发货':
                card_content = 'auto'
            else:
                card_content = 'no'
            now_time = int(time.time())
            payment_api = importlib.import_module("getways." + user_payment_method)
            return_data = payment_api.submit(price, name, trade_id)
            if return_data['status'] == 'Success':
                print('API请求成功')
                if return_data['type'] == 'url':
                    pay_url = return_data['data']
                    keyboard = [[InlineKeyboardButton("点击跳转支付", url=pay_url)]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    message_id=query.edit_message_text(
                        '请在{}s内支付完成，超时支付会导致发货失败！\n'
                        '[点击这里]({})跳转支付，或者点击下方跳转按钮'.format(PAY_TIMEOUT, pay_url),
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    ).message_id
                elif return_data['type'] == 'qr_code':
                    qr_code = return_data['data']
                    message_id=query.edit_message_text(
                        '正在生成支付二维码，请稍后',
                        parse_mode='Markdown',
                    ).message_id
                    bot.delete_message(chat_id=user_id, message_id=message_id)
                    message_id=bot.send_photo(
                        chat_id=chat_id,
                        photo='http://api.qrserver.com/v1/create-qr-code/?data={}&color=7f7f81&bgcolor=ffffcb&margin=16'.format(urllib.parse.quote(qr_code)),
                        caption='请在{}s内支付完成，超时支付会导致发货失败！'.format(PAY_TIMEOUT)
                    ).message_id
                conn = sqlite3.connect('faka.sqlite3')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO trade VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(trade_id, goods_id,  goods_name, description, use_way, card_id,card_content,str(user_id)+'|'+str(message_id), username, now_time, 'unpaid', user_payment_method))
                conn.commit()
                conn.close()
                conn = pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USERNAME,password=DB_PASSWORD,db=DB_DATABASE,cursorclass=pymysql.cursors.DictCursor)
                cursor = conn.cursor()
                cursor.execute("update products set in_stock=in_stock-1 where id=%s", (goods_id,))
                conn.commit()
                cursor.close()
                conn.close()
                
            elif return_data['status'] == 'Failed':
                print(user_payment_method + " 支付接口故障，请前往命令行查看错误信息")
                query.edit_message_text(
                    '订单创建失败：{}，请联系管理员处理！\n'.format(return_data['data']),
                )
                return ConversationHandler.END
        else:
            query.edit_message_text('您存在未支付订单，请支付或等待订单过期后重试！')
            return ConversationHandler.END
    except ModuleNotFoundError:
        print('支付方式不存在，请检查文件名与配置是否一致')
        query.edit_message_text('订单创建失败：支付接口故障，请联系管理员处理！')
        return ConversationHandler.END
    except Exception as e:
        print(e)
        query.edit_message_text('订单创建失败：支付接口故障，请联系管理员处理！')
        return ConversationHandler.END


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
            '介绍：\n{}\n'
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
    update.message.reply_text('期待再次见到你～')
    return ConversationHandler.END


def get_trade_id():
    now_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    random_num = random.randint(0, 99)
    if random_num <= 10:
        random_num = str(0) + str(random_num)
    unique_num = str(now_time) + str(random_num)
    return unique_num


def timeout(update, context):
    update.message.reply_text('会话超时，期待再次见到你～ /start')
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
            trade_id, goods_id,user_id, creat_time, goods_name, description, use_way, card_content, card_id, payment_method,username \
                = i[0], i[1],i[7], i[9], i[2], i[3], i[4], i[6], i[5], i[11], i[8]
            sub_time = now_time - int(creat_time)
            if sub_time >= PAY_TIMEOUT:
                payment_api = importlib.import_module("getways." + payment_method)
                payment_api.cancel(trade_id)
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
                bot.delete_message(chat_id=user_id.split('|')[0], message_id=user_id.split('|')[1])
                bot.send_message(
                    chat_id=int(user_id.split('|')[0]),
                    text='很遗憾，订单已关闭\n'
                         '订单号：`{}`\n'
                         '原因：逾期未付\n'.format(trade_id),
                    parse_mode='Markdown',
                )
            else:
                try:
                    payment_api = importlib.import_module("getways." + payment_method)
                    rst = payment_api.query(trade_id)
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
                        bot.delete_message(chat_id=user_id.split('|')[0], message_id=user_id.split('|')[1])
                        bot.send_message(
                            chat_id=int(user_id.split('|')[0]),
                            text='恭喜！订单支付成功!\n'
                                 '订单号：`{}`\n'
                                 '商品：*{}*\n'
                                 '介绍：\n{}\n'
                                 '卡密内容：`{}`\n'.format(trade_id, goods_name, description, card_context),
                            parse_mode='Markdown',
                        )
                except ModuleNotFoundError:
                    print('支付方式不存在，请检查文件名与配置是否一致')
                except Exception as e:
                    print(e)
            time.sleep(3)
        print('---------------订单轮询结束---------------')
        time.sleep(10)


start_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],

        states={
            ROUTE: [
                CommandHandler('start', start),
                CallbackQueryHandler(category_filter, pattern='^' + str('购买商品') + '$'),
                CallbackQueryHandler(trade_filter, pattern='^' + str('查询订单') + '$'),
            ],
            CATEGORY: [
                CommandHandler('start', start),
                CallbackQueryHandler(goods_filter, pattern='.*?'),
            ],
            PRICE: [
                CommandHandler('start', start),
                CallbackQueryHandler(user_price_filter, pattern='.*?'),
            ],
            CHOOSE_PAYMENT_METHOD: [
                CommandHandler('start', start),
                CallbackQueryHandler(choose_payment_method, pattern='^' + str('提交订单') + '$'),
                CallbackQueryHandler(cancel_trade, pattern='^' + str('下次一定') + '$')
            ],
            SUBMIT: [
                CommandHandler('start', start),
                CallbackQueryHandler(submit_trade, pattern='.*?'),
            ],
            TRADE: [
                CommandHandler('start', start),
                MessageHandler(Filters.text, trade_query)
            ],
            ConversationHandler.TIMEOUT: [MessageHandler(Filters.all, timeout)],
        },
        conversation_timeout=300,
        fallbacks=[CommandHandler('cancel', cancel)]
     )
