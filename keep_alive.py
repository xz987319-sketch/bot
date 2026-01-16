# 保活脚本：启动一个小型Web服务，供UptimeRobot定时访问
from flask import Flask
from threading import Thread

# 创建Flask应用
app = Flask('')

# 定义根路由，访问时返回提示文字
@app.route('/')
def home():
    return "Telegram Bot is alive! 🚀"

# 启动Web服务的函数
def run():
    # 0.0.0.0 允许外部访问，8080是Replit默认端口
    app.run(host='0.0.0.0', port=8080)

# 开启子线程运行Web服务（不阻塞机器人主程序）
def keep_alive():
    t = Thread(target=run)
    t.start()