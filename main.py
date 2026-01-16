# Telegram账户管理机器人 - 修正版（适配v13.x）
import logging
import telegram
from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.utils.request import Request

# -------------------------- 请修改以下配置 --------------------------
BOT_TOKEN = "7725652714:AAEYjcPwbxMrPJ20xHtZXpn0zuTc3qJi2DU"  # 替换为你的Bot Token
PROXY_URL = "socks5://127.0.0.1:7890"  # 替换为你的有效代理地址
# -------------------------------------------------------------------

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# /start命令
def start(update, context):
    welcome_text = '''👋 你好！我是账户管理机器人，帮你查询各类账户信息～

📌【核心功能&使用指南】
1、在群里@我并输入户号 → 查询账户
2、/myid → 查自身 ID
3、发运算式 → 直接计算

⚠️ 群聊需开启「读取+发送消息」权限

有任何问题可直接回复消息，我会尽力解答～～'''
    update.message.reply_text(welcome_text)

# /myid命令
def myid(update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    update.message.reply_text(f'🔍 你的用户ID：{user_id}\n🗨️ 当前聊天ID：{chat_id}')

# 消息回复
def echo(update, context):
    update.message.reply_text(f'你发送的内容：{update.message.text}')

# 错误处理器
def error_handler(update, context):
    logger.error(f"更新 {update} 触发错误：{context.error}")
    if update and update.message:
        update.message.reply_text('😵 抱歉，机器人运行出错了，请稍后再试！')

# 主函数
def main():
    try:
        # 修正：移除v13.x不支持的pool_maxsize参数
        request = Request(
            proxy_url=PROXY_URL,
            connect_timeout=30,
            read_timeout=30
        )

        # 初始化Bot
        bot = Bot(
            token=BOT_TOKEN,
            request=request
        )

        # 初始化Updater
        updater = Updater(bot=bot, use_context=True)
        dp = updater.dispatcher

        # 注册处理器
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("myid", myid))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))
        dp.add_error_handler(error_handler)

        # 启动机器人
        logger.info("✅ 机器人已成功启动！按 Ctrl+C 停止运行")
        updater.start_polling(poll_interval=1.0)
        updater.idle()

    except Exception as e:
        logger.error(f"❌ 机器人启动失败：{str(e)}")
        print(f"\n启动失败！请检查：")
        print(f"1. Bot Token是否正确：{BOT_TOKEN}")
        print(f"2. 代理地址是否有效：{PROXY_URL}")
        print(f"3. 依赖包是否安装完整")
        print(f"错误详情：{str(e)}")

if __name__ == '__main__':
    main()