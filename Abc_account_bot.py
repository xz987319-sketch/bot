import sqlite3
import time
import re
import ast
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext


# ===================== 日志配置（按日期命名，保留90天） =====================
def setup_logger():
    # 确保日志目录存在
    log_dir = "bot_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 配置 logger
    logger = logging.getLogger("AccountBot")
    logger.setLevel(logging.INFO)  # 日志级别：INFO及以上

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 自定义日志文件名生成函数（按日期命名）
    def get_log_filename():
        # 获取当前日期，格式：YYYY-MM-DD
        current_date = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(log_dir, f"{current_date}.log")

    # 配置按日期分割的文件处理器：每天0点生成新日志，保留90天，按日期命名
    file_handler = TimedRotatingFileHandler(
        filename=get_log_filename(),  # 初始文件名（当日日期）
        when="midnight",  # 每天午夜分割
        interval=1,  # 间隔1天
        backupCount=90,  # 保留90天日志
        encoding="utf-8",  # 支持中文
        utc=False  # 使用本地时间（而非UTC时间）
    )

    # 自定义后缀名格式（确保分割后的文件也是日期命名）
    file_handler.suffix = "%Y-%m-%d.log"
    # 修复文件名匹配规则，确保按日期分割时正确命名
    file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}\.log$")

    # 配置日志格式：时间 - 日志级别 - 模块 - 消息
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(module)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)

    # 添加控制台输出处理器（可选，保留控制台打印）
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 添加处理器到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 初始化logger
logger = setup_logger()

# ===================== 数据库表结构说明（重要） =====================
# accounts表字段说明：
# - title: TEXT（主键，账户标题，如“台12”）
# - current_content: TEXT（账户内容，如用户名/密码，⚠️ 非content列）
# 所有操作该表的函数，列名需统一用current_content
# ==================================================================

# -------------------------- 核心配置项（需替换） --------------------------
# 替换为你的Bot Token（从@BotFather获取）
BOT_TOKEN = "7725652714:AAEYjcPwbxMrPJ20xHtZXpn0zuTc3qJi2DU"
# 机器人创建者的ID（初始超级管理员，先运行机器人用/myid获取）
OWNER_ID = 8229811319  # 例如：123456789
# SQLite数据库文件路径（自动创建，无需手动新建）
DB_FILE = "account_bot.db"


# -------------------------- 数据库核心操作函数 --------------------------
# 初始化数据库（创建表+插入初始管理员）
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 1. 管理员表：存储管理员ID（主键，避免重复）
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY)''')

        # 2. 账户表：存储账户标题（主键）和当前内容
        c.execute('''CREATE TABLE IF NOT EXISTS accounts
                     (title TEXT PRIMARY KEY, current_content TEXT)''')

        # 3. 账户历史记录表：存储历史内容，自动记录时间
        c.execute('''CREATE TABLE IF NOT EXISTS account_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      title TEXT,
                      content TEXT,
                      create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY(title) REFERENCES accounts(title))''')

        # 插入初始管理员（避免重复插入）
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))

        conn.commit()
        conn.close()
        logger.info("【数据库初始化】成功创建/连接数据库，初始化表结构")
    except Exception as e:
        logger.error(f"【数据库初始化失败】{str(e)}")


# 检查是否为管理员（通用权限校验函数）
def is_admin(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logger.error(f"【管理员校验失败】用户ID：{user_id} | 错误：{str(e)}")
        return False


# -------------------------- 消息记录工具函数 --------------------------
def record_message(update: Update):
    """记录私聊/群聊的消息内容"""
    user = update.effective_user
    chat = update.effective_chat
    message_text = update.message.text.strip() if update.message.text else "无文本内容"

    user_info = f"用户：{user.username or user.first_name}（ID：{user.id}）"

    # 判断会话类型：私聊/群聊/超级群
    if chat.type == "private":
        chat_type = "私聊"
        chat_info = "会话类型：私聊"
    else:
        chat_type = "群聊"
        chat_info = f"会话类型：群聊 | 群名：{chat.title}（群ID：{chat.id}）"

    # 记录日志
    logger.info(f"【消息记录-{chat_type}】{user_info} | {chat_info} | 消息内容：{message_text}")


# -------------------------- 命令处理函数（核心功能） --------------------------
# 1. 查询自身ID (/myid)
def myid(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    update.message.reply_text(f"你的用户ID是：{user_id}")
    logger.info(f"【/myid命令】用户：{username}（ID：{user_id}）查询了自身ID")


# 2. 处理/start命令：回复问候语+使用指南
def start_command(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    welcome_msg = f"""
👋 你好！我是账户管理机器人，帮你存储 / 查询各类账户信息～

📌【核心功能&使用指南】
1、/list → 管理员查账户列表
2、/add 标题 (换行) 信息 → 管理员增改账户
3、账户标题 @本机器人 → 查询账户
4、/myid → 查自身 ID
5、发运算式 → 直接计算

⚠️ 仅限管理员 /add/list | 换行用 Ctrl+Enter | 群聊需开启「读取+发送消息」权限

有任何问题可直接回复消息，我会尽力解答～
    """
    update.message.reply_text(welcome_msg)
    logger.info(f"【/start命令】用户：{username}（ID：{user_id}）启动了机器人")


# 3. 添加/更新账户 (/add 标题\n内容)
def add_account(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    # 权限校验：仅管理员可操作
    if not is_admin(user_id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可添加账户）")
        logger.warning(f"【/add命令-权限不足】用户：{username}（ID：{user_id}）尝试添加账户")
        return

    # 读取原始消息文本（完整保留换行符）
    full_text = update.message.text.strip()

    # 分离命令和后续内容
    if not full_text.startswith("/add "):
        update.message.reply_text("""❌ 格式错误！正确格式：
/add 账户标题（换行）账户具体信息
📌 操作提示：
1. 输入 "/add 账户1" 后，按【Ctrl+Enter】换行
2. 换行后输入所有账户信息，最后按Enter发送""")
        logger.warning(f"【/add命令-格式错误】用户：{username}（ID：{user_id}）输入：{full_text}")
        return

    # 去掉命令前缀，获取纯内容
    content_after_command = full_text[len("/add "):]

    # 检查是否包含换行符
    if "\n" not in content_after_command:
        update.message.reply_text("""❌ 缺少换行！必须按Ctrl+Enter换行分隔标题和内容
✅ 正确示例：
/add 户号1
用户名：test001
密码：123456""")
        logger.warning(f"【/add命令-缺少换行】用户：{username}（ID：{user_id}）输入：{content_after_command}")
        return

    # 分割标题和内容（仅第一个换行）
    title, account_content = content_after_command.split("\n", 1)
    title = title.strip()
    account_content = account_content.strip()

    # 非空校验
    if not title:
        update.message.reply_text("❌ 账户标题不能为空！")
        logger.warning(f"【/add命令-标题为空】用户：{username}（ID：{user_id}）")
        return
    if not account_content:
        update.message.reply_text("❌ 账户具体信息不能为空！")
        logger.warning(f"【/add命令-内容为空】用户：{username}（ID：{user_id}）标题：{title}")
        return

    # 数据库操作
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 检查账户是否存在
        c.execute("SELECT current_content FROM accounts WHERE title=?", (title,))
        old_content = c.fetchone()

        if old_content:
            # 账户存在：保存历史+更新当前内容
            c.execute("INSERT INTO account_history (title, content) VALUES (?, ?)", (title, old_content[0]))
            c.execute("UPDATE accounts SET current_content=? WHERE title=?", (account_content, title))
            msg = f"""✅ 账户「{title}」已更新！
📌 原内容已保存至历史记录，当前内容：
{account_content}"""
            logger.info(f"【/add命令-更新账户】用户：{username}（ID：{user_id}）更新账户：{title}")
        else:
            # 账户不存在：新增
            c.execute("INSERT INTO accounts (title, current_content) VALUES (?, ?)", (title, account_content))
            msg = f"""✅ 账户「{title}」添加成功！
📌 账户信息：
{account_content}"""
            logger.info(f"【/add命令-新增账户】用户：{username}（ID：{user_id}）新增账户：{title}")

        conn.commit()
        conn.close()
        update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"【/add命令-数据库错误】用户：{username}（ID：{user_id}）| 错误：{str(e)}")
        update.message.reply_text(f"❌ 添加失败：{str(e)}")


# 4. 删除账户 (/delete 标题)
def delete_account(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    if not is_admin(user_id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可删除账户）")
        logger.warning(f"【/delete命令-权限不足】用户：{username}（ID：{user_id}）尝试删除账户")
        return

    if not context.args:
        update.message.reply_text("❌ 格式错误！正确格式：/delete 账户标题")
        logger.warning(f"【/delete命令-格式错误】用户：{username}（ID：{user_id}）未输入标题")
        return

    title = " ".join(context.args).strip()
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 先检查账户是否存在
        c.execute("SELECT 1 FROM accounts WHERE title=?", (title,))
        if not c.fetchone():
            conn.close()
            update.message.reply_text(f"❌ 账户「{title}」不存在！")
            logger.warning(f"【/delete命令-账户不存在】用户：{username}（ID：{user_id}）尝试删除：{title}")
            return

        # 级联删除：先删历史记录，再删账户
        c.execute("DELETE FROM account_history WHERE title=?", (title,))
        c.execute("DELETE FROM accounts WHERE title=?", (title,))

        conn.commit()
        conn.close()
        update.message.reply_text(f"✅ 账户「{title}」已删除（含历史记录）！")
        logger.info(f"【/delete命令-成功】用户：{username}（ID：{user_id}）删除账户：{title}")
    except Exception as e:
        logger.error(f"【/delete命令-数据库错误】用户：{username}（ID：{user_id}）| 错误：{str(e)}")
        update.message.reply_text(f"❌ 删除失败：{str(e)}")


# 5. 列出所有账户 (/list)
def list_accounts(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    if not is_admin(user_id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可查看账户列表）")
        logger.warning(f"【/list命令-权限不足】用户：{username}（ID：{user_id}）尝试查看账户列表")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT title FROM accounts ORDER BY title")
        accounts = c.fetchall()
        conn.close()

        if not accounts:
            update.message.reply_text("📜 暂无任何账户信息！")
            logger.info(f"【/list命令-无账户】用户：{username}（ID：{user_id}）查看账户列表，当前无账户")
            return

        # 拼接账户列表
        account_list = "📜 所有账户标题：\n"
        for idx, (title,) in enumerate(accounts, 1):
            account_list += f"{idx}. {title}\n"
        update.message.reply_text(account_list)
        logger.info(f"【/list命令-成功】用户：{username}（ID：{user_id}）查看账户列表，共{len(accounts)}个账户")
    except Exception as e:
        logger.error(f"【/list命令-数据库错误】用户：{username}（ID：{user_id}）| 错误：{str(e)}")
        update.message.reply_text(f"❌ 查询失败：{str(e)}")


# 6. 添加管理员 (/addadmin 用户ID)
def add_admin(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    # 权限修改：所有管理员均可添加管理员（原规则：仅OWNER_ID可操作）
    if not is_admin(user_id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可添加管理员）")
        logger.warning(f"【/addadmin命令-权限不足】用户：{username}（ID：{user_id}）尝试添加管理员")
        return

    if not context.args:
        update.message.reply_text("❌ 格式错误！正确格式：/addadmin 管理员ID")
        logger.warning(f"【/addadmin命令-格式错误】用户：{username}（ID：{user_id}）未输入管理员ID")
        return

    try:
        admin_id = int(context.args[0])
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 避免重复添加
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
        if c.rowcount == 0:
            msg = f"❌ ID「{admin_id}」已是管理员！"
            logger.warning(f"【/addadmin命令-重复添加】用户：{username}（ID：{user_id}）尝试添加：{admin_id}")
        else:
            msg = f"✅ 管理员「{admin_id}」添加成功！"
            logger.info(f"【/addadmin命令-成功】用户：{username}（ID：{user_id}）添加管理员：{admin_id}")

        conn.commit()
        conn.close()
        update.message.reply_text(msg)
    except ValueError:
        update.message.reply_text("❌ 管理员ID必须是数字！")
        logger.warning(f"【/addadmin命令-格式错误】用户：{username}（ID：{user_id}）输入非数字ID：{context.args[0]}")
    except Exception as e:
        logger.error(f"【/addadmin命令-数据库错误】用户：{username}（ID：{user_id}）| 错误：{str(e)}")
        update.message.reply_text(f"❌ 添加失败：{str(e)}")


# 7. 移除管理员 (/removeadmin 管理员ID)
def remove_admin(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    if user_id != OWNER_ID:
        update.message.reply_text("❌ 仅机器人创建者可移除管理员！")
        logger.warning(f"【/removeadmin命令-权限不足】用户：{username}（ID：{user_id}）尝试移除管理员")
        return

    if not context.args:
        update.message.reply_text("❌ 格式错误！正确格式：/removeadmin 管理员ID")
        logger.warning(f"【/removeadmin命令-格式错误】用户：{username}（ID：{user_id}）未输入管理员ID")
        return

    try:
        admin_id = int(context.args[0])
        # 禁止移除超级管理员
        if admin_id == OWNER_ID:
            update.message.reply_text("❌ 无法移除超级管理员（机器人创建者）！")
            logger.warning(f"【/removeadmin命令-禁止操作】用户：{username}（ID：{user_id}）尝试移除超级管理员")
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE user_id=?", (admin_id,))

        if c.rowcount == 0:
            msg = f"❌ ID「{admin_id}」不是管理员！"
            logger.warning(f"【/removeadmin命令-非管理员】用户：{username}（ID：{user_id}）尝试移除：{admin_id}")
        else:
            msg = f"✅ 管理员「{admin_id}」移除成功！"
            logger.info(f"【/removeadmin命令-成功】用户：{username}（ID：{user_id}）移除管理员：{admin_id}")

        conn.commit()
        conn.close()
        update.message.reply_text(msg)
    except ValueError:
        update.message.reply_text("❌ 管理员ID必须是数字！")
        logger.warning(f"【/removeadmin命令-格式错误】用户：{username}（ID：{user_id}）输入非数字ID：{context.args[0]}")
    except Exception as e:
        logger.error(f"【/removeadmin命令-数据库错误】用户：{username}（ID：{user_id}）| 错误：{str(e)}")
        update.message.reply_text(f"❌ 移除失败：{str(e)}")


# 8. 查看管理员列表 (/admins) - 核心修改函数
def list_admins(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    if not is_admin(user_id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可查看管理员列表）")
        logger.warning(f"【/admins命令-权限不足】用户：{username}（ID：{user_id}）尝试查看管理员列表")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins ORDER BY user_id")
        admin_ids = [row[0] for row in c.fetchall()]
        conn.close()

        if not admin_ids:
            update.message.reply_text("👑 暂无管理员！")
            logger.info(f"【/admins命令-无管理员】用户：{username}（ID：{user_id}）查看管理员列表，当前无管理员")
            return

        # 拼接管理员列表：名字 + 姓氏 + @用户名 + ID + 超级管理员标记
        admin_list = "👑 管理员列表：\n"
        for idx, admin_id in enumerate(admin_ids, 1):
            try:
                user = context.bot.get_chat(admin_id)
                # 调整姓名顺序：先名字（first_name），后姓氏（last_name）
                full_name = []
                if user.first_name:
                    full_name.append(user.first_name)
                if user.last_name:
                    full_name.append(user.last_name)
                full_name_str = " ".join(full_name) if full_name else "未知姓名"

                # 处理用户名：有则显示@xxx，无则显示“无用户名”
                username_str = f"@{user.username}" if user.username else "无用户名"
            except Exception:
                full_name_str = "未知姓名"
                username_str = "无用户名"

            # 超级管理员标记
            tag = "（超级管理员）" if admin_id == OWNER_ID else ""
            # 最终格式：序号. 名字 姓氏 @用户名（ID：xxx） 标记
            admin_list += f"{idx}. {full_name_str} {username_str}（ID：{admin_id}）{tag}\n"

        update.message.reply_text(admin_list)
        logger.info(f"【/admins命令-成功】用户：{username}（ID：{user_id}）查看管理员列表，共{len(admin_ids)}个管理员")
    except Exception as e:
        logger.error(f"【/admins命令-数据库错误】用户：{username}（ID：{user_id}）| 错误：{str(e)}")
        update.message.reply_text(f"❌ 查询失败：{str(e)}")


# 9. 查看账户历史记录 (/history 标题)
def view_history(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    if not is_admin(user_id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可查看历史记录）")
        logger.warning(f"【/history命令-权限不足】用户：{username}（ID：{user_id}）尝试查看历史记录")
        return

    if not context.args:
        update.message.reply_text("❌ 格式错误！正确格式：/history 账户标题")
        logger.warning(f"【/history命令-格式错误】用户：{username}（ID：{user_id}）未输入标题")
        return

    title = " ".join(context.args).strip()
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 先检查账户是否存在
        c.execute("SELECT 1 FROM accounts WHERE title=?", (title,))
        if not c.fetchone():
            conn.close()
            update.message.reply_text(f"❌ 账户「{title}」不存在！")
            logger.warning(f"【/history命令-账户不存在】用户：{username}（ID：{user_id}）尝试查看：{title}")
            return

        # 倒序查询历史记录
        c.execute('''SELECT content, create_time FROM account_history 
                     WHERE title=? ORDER BY create_time DESC''', (title,))
        history = c.fetchall()
        conn.close()

        if not history:
            update.message.reply_text(f"📜 账户「{title}」暂无历史记录！")
            logger.info(f"【/history命令-无历史】用户：{username}（ID：{user_id}）查看账户：{title} 历史记录，当前无记录")
            return

        # 拼接历史记录
        history_text = f"📜 账户「{title}」历史记录（倒序）：\n"
        for idx, (content, create_time) in enumerate(history, 1):
            history_text += f"\n{idx}. 记录时间：{create_time}\n内容：{content}\n"
        update.message.reply_text(history_text)
        logger.info(f"【/history命令-成功】用户：{username}（ID：{user_id}）查看账户：{title} 历史记录，共{len(history)}条")
    except Exception as e:
        logger.error(f"【/history命令-数据库错误】用户：{username}（ID：{user_id}）| 错误：{str(e)}")
        update.message.reply_text(f"❌ 查询失败：{str(e)}")


# -------------------------- 计算功能核心函数（带调试日志） --------------------------
# 校验输入是否为合法的运算表达式
def is_valid_calculation(expr):
    # 包含@则直接判定为非运算表达式
    if '@' in expr:
        logger.debug(f"【计算调试-校验失败】表达式含@符号：{expr}")
        return False
    # 仅允许数字、+-*/、括号、小数点、空格
    valid_chars = r'^[\d\+\-\*\/\(\)\.\s]+$'
    if not re.match(valid_chars, expr):
        logger.warning(f"【计算调试-校验失败】表达式含非法字符：{expr}")
        return False
    # 必须包含至少一个运算符号
    if not any(op in expr for op in ['+', '-', '*', '/']):
        logger.warning(f"【计算调试-校验失败】表达式无运算符号：{expr}")
        return False
    logger.info(f"【计算调试-校验成功】表达式合法：{expr}")
    return True


# 安全计算表达式（支持运算优先级，带调试日志）
def calculate_expression(expr):
    try:
        # 调试日志：原始输入表达式
        logger.info(f"【计算调试-原始输入】：{expr}")

        expr_clean = expr.replace(' ', '')
        # 调试日志：处理后（去除空格）的表达式
        logger.info(f"【计算调试-处理后表达式】：{expr_clean}")

        # 安全解析表达式，防止恶意代码
        ast.parse(expr_clean, mode='eval')
        result = eval(expr_clean)

        # 处理浮点数转整数（如15.0→15）
        if isinstance(result, float) and result.is_integer():
            result = int(result)

        # 调试日志：计算结果
        logger.info(f"【计算调试-最终结果】：{expr} = {result}")

        return f"✅ 计算结果：\n{expr} = {result}"
    except ZeroDivisionError:
        error_msg = "❌ 计算错误：除数不能为0！"
        logger.error(f"【计算调试-错误】{error_msg} | 表达式：{expr}")
        return error_msg
    except SyntaxError:
        error_msg = "❌ 计算错误：表达式格式不合法（如缺少操作数、括号不匹配等）！"
        logger.error(f"【计算调试-错误】{error_msg} | 表达式：{expr}")
        return error_msg
    except Exception as e:
        error_msg = f"❌ 计算失败：{str(e)}"
        logger.error(f"【计算调试-异常】{error_msg} | 表达式：{expr}")
        return error_msg


# -------------------------- 合并消息处理器（计算+@查询） --------------------------
def unified_message_handler(update: Update, context: CallbackContext):
    # 记录消息
    record_message(update)

    user_id = update.effective_user.id
    username = update.effective_user.username or "未知用户名"
    msg_text = update.message.text.strip()

    # 跳过命令消息（交给命令处理器）
    if msg_text.startswith('/'):
        return

    # 第一步：处理计算功能（优先）
    if is_valid_calculation(msg_text):
        reply_msg = calculate_expression(msg_text)
        update.message.reply_text(reply_msg)
        return

    # 第二步：处理@查询/私聊查询
    bot_username = context.bot.username
    is_at_query = f"@{bot_username}" in msg_text
    if is_at_query:
        account_title = msg_text.split(f"@{bot_username}")[0].strip()
        # 数据库查询
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT current_content FROM accounts WHERE title = ?", (account_title,))
            result = cursor.fetchone()
            conn.close()

            logger.info(f"【@查询调试-结果】用户：{username}（ID：{user_id}）| 账户：{account_title} | 查询结果：{result}")

            # 回复逻辑：有则返回信息，无则提示不存在，无额外列表
            if result:
                update.message.reply_text(f"📋 账户「{account_title}」的信息：\n{result[0]}")
            else:
                update.message.reply_text(f"❌ 账户「{account_title}」不存在！")
        except Exception as e:
            logger.error(f"【@查询调试-数据库错误】用户：{username}（ID：{user_id}）| 错误：{str(e)}")
            update.message.reply_text(f"❌ 查询失败：{str(e)}")
        return

    # 非计算、非@查询的内容，无任何回复
    return


# -------------------------- 机器人启动入口 --------------------------
def main():
    # 初始化数据库
    init_db()

    # 创建Updater和Dispatcher
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher

    # 注册所有命令处理器
    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("myid", myid))
    dp.add_handler(CommandHandler("add", add_account))
    dp.add_handler(CommandHandler("delete", delete_account))
    dp.add_handler(CommandHandler("list", list_accounts))
    dp.add_handler(CommandHandler("addadmin", add_admin))
    dp.add_handler(CommandHandler("removeadmin", remove_admin))
    dp.add_handler(CommandHandler("admins", list_admins))
    dp.add_handler(CommandHandler("history", view_history))

    # 注册合并后的消息处理器（计算+@查询）
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, unified_message_handler))

    # 启动机器人
    logger.info("【机器人启动】账户管理机器人已成功启动，按Ctrl+C停止...")
    print("机器人已启动，按Ctrl+C停止...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()