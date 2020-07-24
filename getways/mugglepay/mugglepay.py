import requests
import json
import sqlite3

# mugglepay密钥
TOKEN = ''

# 支付后返回地址
RETURN_URL = "https://ilay1678.github.io/pages/pay/success.html"


def submit(money, name, trade_id):
    header={
        "token": TOKEN
    }
    data = {'merchant_order_id': trade_id,'price_amount':money,'price_currency':'CNY','success_url':RETURN_URL,'title':'发卡机器人'}
    print(data)
    try:
        req = requests.post('https://api.mugglepay.com/v1/orders',headers=header, data=data)
        rst_dict = json.loads(req.text)
        if rst_dict['status'] == 201:
            pay_url = rst_dict['payment_url']
            return_data = {
                'status': 'Success',
                'type': 'url',
                'data': pay_url
            }
            conn = sqlite3.connect('faka.sqlite3')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO getways VALUES (?,?)",
                                   (trade_id, rst_dict['order']['order_id'],))
            conn.commit()
            conn.close()
            return return_data
        else:
            return_data = {
                'status': 'Failed',
                'data': rst_dict['error']
            }
            return return_data
    except Exception as e:
        print('submit | API请求失败')
        print(e)
        return_data = {
            'status': 'Failed',
            'data': 'API请求失败'
        }
        return return_data


def query(out_trade_no):
    conn = sqlite3.connect('faka.sqlite3')
    cursor = conn.cursor()
    cursor.execute('select * from getways where id=?', (out_trade_no,))
    mugglepay_list = cursor.fetchone()
    conn.close()
    order_id=mugglepay_list[1]
    header={
        "token": TOKEN
    }
    try:
        req = requests.get('https://api.mugglepay.com/v1/orders/{}'.format(order_id,),headers=header)
        rst_dict = json.loads(req.text)
        print(rst_dict)
        if rst_dict['status'] == 200 :
            pay_status = str(rst_dict['order']['status'])
            if pay_status == 'PAID':
                print('支付成功')
                return '支付成功'
            else:
                print('支付失败')
                return '支付失败'
        else:
            print('查询失败，订单号不存在')
            return '查询失败，订单号不存在'
    except Exception as e:
        print(e)
        print('epay | 查询请求失败')
        return 'API请求失败'


def cancel(out_trade_no):
    print('订单已经取消')
