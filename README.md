## 介绍
这是一个Telegram 发卡机器人，此机器人基于Python开发，在Python 3.6.7测试通过。
Telegram 交流反馈群组：@tgfaka  [点击加入](https://t.me/tgfaka)

## 使用方法
### 安装依赖
`pip3 install -r requirements.txt` 
### 编辑配置
编辑`config.py.example`文件，重命名为`config.py`，根据注释配置参数
### 启动方法
`python3 main.py`

## 功能介绍
### 管理员界面
![](https://s3.jpg.cm/2020/06/29/cwB5y.jpg)
![](https://s3.jpg.cm/2020/06/29/cw0LC.jpg)
![](https://s3.jpg.cm/2020/06/29/cw2bt.jpg)
![](https://s3.jpg.cm/2020/06/29/cwg25.jpg)
![](https://s3.jpg.cm/2020/06/29/cwfNr.jpg)
### 整体功能演示
[演示视频](https://github.com/lulafun/tg_faka_bot/raw/master/fakabot.mp4)
### 数据库
使用sqlite3作为数据库，轻量、便于备份。
### 支付成功跳转页面
可以自定义，本程序判断是否支付成功并不是通过支付回调，而是采用向聚合支付接口轮询实现
### 支付接口
支付接口基于易支付、支付宝当面付
为什么选择易支付？因为做易支付的聚合支付比较多
由于市面上有许多的易支付版本，虽然接口传参一样，但是有些网站的返回值还是有所不同，目前该程序对我所使用过的易支付站点做了适配，如有不适配的情况，可以积极反馈

#### 配置自己的支付接口，
编辑`config.py`文件
现在存在的支付接口：
```
PAYMENT_METHOD = {
    'epay': {'epay': '支付宝/微信/QQ'},
    'alifacepay': {'alifacepay': '支付宝当面付'}
}
```

如果这时候有一个新的文件名为`wepay.py`的支付接口，那么可以这么配置：
```
PAYMENT_METHOD = {
    'epay': {'epay': '支付宝/微信/QQ'},
    'alifacepay': {'alifacepay': '支付宝当面付'},
    'wepay': {'wepay': '微信支付'},
    '文件夹':{'文件1': '支付宝','文件2': '微信支付'},
}
```

`wepay.py`的相对路径为`getways/wepay/wepay.py`，请确保你安装了此插件需要的额外依赖


### 编写自己的支付接口
在这个版本中重新设计了支付接口模块，那么也就意味着大家也可以对接自己想要的接口
```
├── getways
│   ├── alifacepay
│   │   ├── alifacepay.py
│   │   └── alifacepay.txt
│   └── epay
│       └── epay.py
```
支付接口名为文件名，以支付宝当面付为例，支付接口文件为`getways/alifacepay/alifacepay.py`，同目录下的`alifacepay.txt`为此接口所需依赖，增加接口时需要额外安装此文件中列出的依赖，安装方法为`pip3 install -r alifacepay.txt`

#### 传参与返回值
支付接口文件拥有三个函数，分别为`submit`、`query`、`cancel`
三个函数的传参分别为：
```
submit(price, subject, trade_id)
价格、订单名、订单号
query(out_trade_no)
订单号
cancel(out_trade_no)
订单号
```
##### submit
`submit`返回类型为字典，成功返回的`data`分两种类型，由`type`指定。
`url`指的是跳转网页支付链接，案例为易支付；
`qr_code`指的是由字典`data`的键值生成二维码，用户扫描支付，案例为支付宝当面付。
```
成功：
return_data = {
    'status': 'Success',
    'type': 'qr_code',  # url / qr_code
    'data': pr_code
}

失败：
return_data = {
    'status': 'Failed',
    'data': 'API请求失败'
}
```
##### query
由传入订单号查询支付状态
```
成功：
return '支付成功'

失败：
return '支付失败'
```

##### cancel
在支付平台取消传入订单号所指定的订单，有些平台不能创建过多额未支付订单，所以就需要此取消订单操作

此函数无返回值，即使不需要取消订单也不能省略此函数，可`pass`处理


