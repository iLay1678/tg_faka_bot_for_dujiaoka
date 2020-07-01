# epay SDK By Python
from config import API, ID, KEY, JUMP_URL
import requests
import hashlib
import json
import re


def make_data_dict(money, name, trade_id):
    data = {'pid': ID, 'sitename': 'Faka_Bot'}
    data.update(notify_url=JUMP_URL, return_url=JUMP_URL, money=money, name=name, out_trade_no=trade_id)
    return data


def epay_submit(order_data):
    items = order_data.items()
    items = sorted(items)
    wait_sign_str = ''
    for i in items:
        wait_sign_str += str(i[0]) + '=' + str(i[1]) + '&'
    wait_for_sign_str = wait_sign_str[:-1] + KEY
    sign = hashlib.md5(wait_for_sign_str.encode('utf-8')).hexdigest()
    order_data.update(sign=sign, sign_type='MD5')
    try:
        req = requests.post(API + 'submit.php', data=order_data)
        # print(req.text)
        content = re.search(r"<script>(.*)</script>", req.text).group(1)
        # print(content)
        if 'http' in content:
            pay_url = re.search(r"href=\'(.*)\'", content).group(1)
            return pay_url
        else:
            pay_url = API + re.search(r"\.\/(.*)\'", content).group(1)
            print(pay_url)
            trade_no = re.search(r'trade_no=(\d*)', content).group(1)
            print(trade_no)
            site_name = re.search(r"sitename=(.+?)'", content).group(1)
            print(site_name)
            return pay_url
    except Exception as e:
        print('submit | API请求失败')
        print(e)
        return 'API请求失败'


def check_status(out_trade_no):
    try:
        req = requests.get(API + 'api.php?act=order&pid={}&key={}&out_trade_no={}'.format(ID, KEY, out_trade_no), timeout=5)
        # print(req.text)
        rst = re.search(r"(\{.*?\})", req.text).group(1)
        # print(rst)
        rst_dict = json.loads(rst)
        # print(rst_dict)
        code = str(rst_dict['code'])
        if int(code) == 1:
            # trade_no = str(rst_dict['trade_no'])
            # msg = str(rst_dict['msg'])
            pay_status = str(rst_dict['status'])
            if pay_status == '1':
                print('支付成功')
                return '支付成功'
            else:
                print('支付失败')
                return '支付失败'
        else:
            print('查询失败，订单号不存在')
            return '查询失败，订单号不存在'
    except Exception as e:
        print('check_status | 请求失败')
        print(e)
        return 'API请求失败'