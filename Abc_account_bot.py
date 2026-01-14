import sqlite3
import time
import re
import ast
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

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
    # 连接数据库（不存在则自动创建）
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


# 检查是否为管理员（通用权限校验函数）
def is_admin(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None


# -------------------------- 命令处理函数（核心功能） --------------------------
# 1. 查询自身ID (/myid)
def myid(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    update.message.reply_text(f"你的用户ID是：{user_id}")


# 2. 处理/start命令：回复问候语+使用指南
def start_command(update: Update, context: CallbackContext):
    welcome_msg = f"""
👋 你好！我是账户管理机器人，可帮你存储/查询各类账户信息～

📌 【核心功能&使用指南】
1. 查看账户列表（管理员）：发送 /list
2. 添加/更新账户（管理员）：
   格式：/add 账户标题（Ctrl+Enter换行）账户信息
   示例：
   /add 办公邮箱
   用户名：test@xxx.com
   密码：123456
3. 群聊/私聊查询账户：
   格式：账户标题 @{context.bot.username}
   示例：办公邮箱 @Abc_account_bot
4. 查看自己的ID：发送 /myid
5. 计算功能：直接发送运算表达式（如800+500、10*2+8/2）

⚠️ 【注意事项】
• /add、/list 仅管理员可使用，普通用户仅能查询/计算；
• 添加账户时，务必用Ctrl+Enter换行（不是Enter发送）；
• 群聊查询需先将机器人权限勾选「读取消息+发送消息」。

有任何问题可直接回复消息，我会尽力解答～
    """
    update.message.reply_text(welcome_msg)


# 3. 添加/更新账户 (/add 标题\n内容)
def add_account(update: Update, context: CallbackContext):
    """
    添加/更新账户信息（管理员专属）
    🔔 关键注意事项：
    - 插入数据库时，列名需与accounts表的`current_content`保持一致；
    - 使用REPLACE INTO实现“存在则更新，不存在则添加”的逻辑。
    """
    # 权限校验：仅管理员可操作
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可添加账户）")
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
        return

    # 分割标题和内容（仅第一个换行）
    title, account_content = content_after_command.split("\n", 1)
    title = title.strip()
    account_content = account_content.strip()

    # 非空校验
    if not title:
        update.message.reply_text("❌ 账户标题不能为空！")
        return
    if not account_content:
        update.message.reply_text("❌ 账户具体信息不能为空！")
        return

    # 数据库操作
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
    else:
        # 账户不存在：新增
        c.execute("INSERT INTO accounts (title, current_content) VALUES (?, ?)", (title, account_content))
        msg = f"""✅ 账户「{title}」添加成功！
📌 账户信息：
{account_content}"""

    conn.commit()
    conn.close()
    update.message.reply_text(msg)


# 4. 删除账户 (/delete 标题)
def delete_account(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可删除账户）")
        return

    if not context.args:
        update.message.reply_text("❌ 格式错误！正确格式：/delete 账户标题")
        return

    title = " ".join(context.args).strip()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 检查账户是否存在
    c.execute("SELECT 1 FROM accounts WHERE title=?", (title,))
    if not c.fetchone():
        conn.close()
        update.message.reply_text(f"❌ 账户「{title}」不存在！")
        return

    # 级联删除：先删历史记录，再删账户
    c.execute("DELETE FROM account_history WHERE title=?", (title,))
    c.execute("DELETE FROM accounts WHERE title=?", (title,))

    conn.commit()
    conn.close()
    update.message.reply_text(f"✅ 账户「{title}」已删除（含历史记录）！")


# 5. 列出所有账户 (/list)
def list_accounts(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可查看账户列表）")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT title FROM accounts ORDER BY title")
    accounts = c.fetchall()
    conn.close()

    if not accounts:
        update.message.reply_text("📜 暂无任何账户信息！")
        return

    # 拼接账户列表
    account_list = "📜 所有账户标题：\n"
    for idx, (title,) in enumerate(accounts, 1):
        account_list += f"{idx}. {title}\n"
    update.message.reply_text(account_list)


# 6. 添加管理员 (/addadmin 用户ID)
def add_admin(update: Update, context: CallbackContext):
    # 仅超级管理员可添加管理员
    if update.effective_user.id != OWNER_ID:
        update.message.reply_text("❌ 仅机器人创建者可添加管理员！")
        return

    if not context.args:
        update.message.reply_text("❌ 格式错误！正确格式：/addadmin 管理员ID")
        return

    try:
        admin_id = int(context.args[0])
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 避免重复添加
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
        if c.rowcount == 0:
            msg = f"❌ ID「{admin_id}」已是管理员！"
        else:
            msg = f"✅ 管理员「{admin_id}」添加成功！"

        conn.commit()
        conn.close()
        update.message.reply_text(msg)
    except ValueError:
        update.message.reply_text("❌ 管理员ID必须是数字！")


# 7. 移除管理员 (/removeadmin 管理员ID)
def remove_admin(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        update.message.reply_text("❌ 仅机器人创建者可移除管理员！")
        return

    if not context.args:
        update.message.reply_text("❌ 格式错误！正确格式：/removeadmin 管理员ID")
        return

    try:
        admin_id = int(context.args[0])
        # 禁止移除超级管理员
        if admin_id == OWNER_ID:
            update.message.reply_text("❌ 无法移除超级管理员（机器人创建者）！")
            return

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE user_id=?", (admin_id,))

        if c.rowcount == 0:
            msg = f"❌ ID「{admin_id}」不是管理员！"
        else:
            msg = f"✅ 管理员「{admin_id}」移除成功！"

        conn.commit()
        conn.close()
        update.message.reply_text(msg)
    except ValueError:
        update.message.reply_text("❌ 管理员ID必须是数字！")


# 8. 查看管理员列表 (/admins)
def list_admins(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可查看管理员列表）")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins ORDER BY user_id")
    admins = c.fetchall()
    conn.close()

    if not admins:
        update.message.reply_text("👑 暂无管理员！")
        return

    admin_list = "👑 管理员列表：\n"
    for idx, (admin_id,) in enumerate(admins, 1):
        # 标记超级管理员
        tag = "（超级管理员）" if admin_id == OWNER_ID else ""
        admin_list += f"{idx}. {admin_id} {tag}\n"
    update.message.reply_text(admin_list)


# 9. 查看账户历史记录 (/history 标题)
def view_history(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可查看历史记录）")
        return

    if not context.args:
        update.message.reply_text("❌ 格式错误！正确格式：/history 账户标题")
        return

    title = " ".join(context.args).strip()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 检查账户是否存在
    c.execute("SELECT 1 FROM accounts WHERE title=?", (title,))
    if not c.fetchone():
        conn.close()
        update.message.reply_text(f"❌ 账户「{title}」不存在！")
        return

    # 倒序查询历史记录
    c.execute('''SELECT content, create_time FROM account_history 
                 WHERE title=? ORDER BY create_time DESC''', (title,))
    history = c.fetchall()
    conn.close()

    if not history:
        update.message.reply_text(f"📜 账户「{title}」暂无历史记录！")
        return

    # 拼接历史记录
    history_text = f"📜 账户「{title}」历史记录（倒序）：\n"
    for idx, (content, create_time) in enumerate(history, 1):
        history_text += f"\n{idx}. 记录时间：{create_time}\n内容：{content}\n"
    update.message.reply_text(history_text)


# -------------------------- 计算功能核心函数（新增调试日志） --------------------------
# 校验输入是否为合法的运算表达式
def is_valid_calculation(expr):
    # 包含@则直接判定为非运算表达式
    if '@' in expr:
        return False
    # 仅允许数字、+-*/、括号、小数点、空格
    valid_chars = r'^[\d\+\-\*\/\(\)\.\s]+$'
    if not re.match(valid_chars, expr):
        print(f"【计算调试-校验失败】表达式包含非法字符：{expr}")
        return False
    # 必须包含至少一个运算符号
    if not any(op in expr for op in ['+', '-', '*', '/']):
        print(f"【计算调试-校验失败】表达式无运算符号：{expr}")
        return False
    print(f"【计算调试-校验成功】表达式合法：{expr}")
    return True


# 安全计算表达式（支持运算优先级，新增调试日志）
def calculate_expression(expr):
    try:
        # 调试日志：原始输入表达式
        print(f"【计算调试-原始输入】：{expr}")

        expr_clean = expr.replace(' ', '')
        # 调试日志：处理后（去除空格）的表达式
        print(f"【计算调试-处理后表达式】：{expr_clean}")
        # 安全解析表达式，防止恶意代码
        ast.parse(expr_clean, mode='eval')
        result = eval(expr_clean)
        # 处理浮点数转整数（如15.0→15）
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        # 调试日志：计算结果
        print(f"【计算调试-最终结果】：{expr} = {result}")

        return f"✅ 计算结果：\n{expr} = {result}"
    except ZeroDivisionError:
        return "❌ 计算错误：除数不能为0！"
        print(f"【计算调试-错误】{error_msg} | 表达式：{expr}")
        return error_msg
    except SyntaxError:
        return "❌ 计算错误：表达式格式不合法（如缺少操作数、括号不匹配等）！"
        print(f"【计算调试-错误】{error_msg} | 表达式：{expr}")
        return error_msg
    except Exception as e:
        return f"❌ 计算失败：{str(e)}"
        print(f"【计算调试-异常】{error_msg} | 表达式：{expr}")
        return error_msg


# -------------------------- 合并消息处理器（计算+@查询） --------------------------
def unified_message_handler(update: Update, context: CallbackContext):
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
    if f"@{bot_username}" in msg_text:
        account_title = msg_text.split(f"@{bot_username}")[0].strip()
    else:
        account_title = msg_text.strip()

    # 调试日志
    print(f"【@查询调试】原始消息：{msg_text}")
    print(f"【@查询调试】提取的账户标题：{account_title}")

    # 数据库查询
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT current_content FROM accounts WHERE title = ?", (account_title,))
        result = cursor.fetchone()
        conn.close()

        print(f"【@查询调试】数据库查询结果：{result}")

        # 回复逻辑
        if result:
            update.message.reply_text(f"📋 账户「{account_title}」的信息：\n{result[0]}")
        else:
            # 提示已有账户列表
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM accounts")
            titles = [row[0] for row in cursor.fetchall()]
            conn.close()
            existing_titles = "、".join(titles) if titles else "无"
            update.message.reply_text(f"❌ 未找到账户「{account_title}」！\n👉 已有的账户：{existing_titles}")
    except Exception as e:
        print(f"【@查询调试】数据库错误：{str(e)}")
        update.message.reply_text(f"❌ 查询失败：{str(e)}")


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
    print("机器人已启动，按Ctrl+C停止...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()