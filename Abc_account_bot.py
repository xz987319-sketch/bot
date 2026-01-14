import sqlite3
import time
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

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

    # 3. 账户历史记录表：存储历史内容，自动记录时间，支持倒序查询
    c.execute('''CREATE TABLE IF NOT EXISTS account_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT,
                  content TEXT,
                  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(title) REFERENCES accounts(title))''')

    # 插入初始管理员（机器人创建者，避免重复插入）
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))

    # 提交修改并关闭连接
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

'''
# 2. 添加/更新账户 (/add 标题\n内容)
def add_account(update: Update, context: CallbackContext):
    # 权限校验：仅管理员可操作
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可添加账户）")
        return

    # 解析输入参数（保留原始空格和换行）
    if not context.args:
        update.message.reply_text("""❌ 格式错误！正确格式：
/add 账户标题（换行）账户具体信息
📌 操作提示：
1. 输入 "/add 账户1" 后，按【Ctrl+Enter】换行（不是Enter发送）
2. 换行后输入所有账户信息，最后按Enter发送""")
        return

    # 拼接完整输入（还原用户输入的换行，context.args会把换行保留为\n）
    full_input = " ".join(context.args)
    # 严格检查是否包含第一次换行
    if "\n" not in full_input:
        update.message.reply_text("""❌ 缺少换行！必须按Ctrl+Enter换行分隔标题和内容
✅ 正确示例：
/add 户号1
用户名：test001
密码：123456
地址：xxx
📌 注意：
- Ctrl+Enter = 换行（在输入框内换行）
- Enter = 发送（把消息发给机器人）""")
        return

    # 仅分割第一个换行（确保第一次换行后的所有内容都是账户信息）
    title, content = full_input.split("\n", 1)
    title = title.strip()  # 去除标题前后空格（避免"户号1 "和"户号1"被识别为不同标题）
    content = content.strip()  # 去除内容首尾空格（保留内容内部换行）

    # 校验标题和内容非空
    if not title:
        update.message.reply_text("❌ 账户标题不能为空！")
        return
    if not content:
        update.message.reply_text("❌ 账户具体信息不能为空！")
        return

    # 数据库操作：先查账户是否存在，存在则保存历史，再更新；不存在则新增
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 检查账户是否存在
    c.execute("SELECT current_content FROM accounts WHERE title=?", (title,))
    old_content = c.fetchone()

    if old_content:
        # 账户存在：1. 把旧内容存入历史 2. 更新当前内容
        c.execute("INSERT INTO account_history (title, content) VALUES (?, ?)", (title, old_content[0]))
        c.execute("UPDATE accounts SET current_content=? WHERE title=?", (content, title))
        msg = f"""✅ 账户「{title}」已更新！
📌 原内容已保存至历史记录，当前内容：
{content}"""
    else:
        # 账户不存在：新增账户
        c.execute("INSERT INTO accounts (title, current_content) VALUES (?, ?)", (title, content))
        msg = f"""✅ 账户「{title}」添加成功！
📌 账户信息：
{content}"""

    conn.commit()
    conn.close()
    update.message.reply_text(msg)
'''


# 2. 添加/更新账户 (/add 标题\n内容)
def add_account(update: Update, context: CallbackContext):
    # 权限校验：仅管理员可操作
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 你没有权限执行此操作（仅管理员可添加账户）")
        return

    # 读取原始消息文本（完整保留换行符，关键修复！）
    full_text = update.message.text.strip()

    # 第一步：分离命令（/add）和后续内容
    if not full_text.startswith("/add "):
        update.message.reply_text("""❌ 格式错误！正确格式：
/add 账户标题（换行）账户具体信息
📌 操作提示：
1. 输入 "/add 账户1" 后，按【Ctrl+Enter】换行（不是Enter发送）
2. 换行后输入所有账户信息，最后按Enter发送""")
        return

    # 去掉命令前缀 "/add "，获取纯内容（标题+换行+账户信息）
    content_after_command = full_text[len("/add "):]

    # 第二步：检查是否包含换行符
    if "\n" not in content_after_command:
        update.message.reply_text("""❌ 缺少换行！必须按Ctrl+Enter换行分隔标题和内容
✅ 正确示例：
/add 户号1
用户名：test001
密码：123456
地址：xxx
📌 注意：
- Ctrl+Enter = 换行（在输入框内换行）
- Enter = 发送（把消息发给机器人）""")
        return

    # 第三步：仅分割第一个换行（标题=换行前，内容=换行后所有）
    title, account_content = content_after_command.split("\n", 1)
    title = title.strip()  # 去除标题前后空格
    account_content = account_content.strip()  # 去除内容首尾空格（保留内部换行）

    # 第四步：非空校验
    if not title:
        update.message.reply_text("❌ 账户标题不能为空！")
        return
    if not account_content:
        update.message.reply_text("❌ 账户具体信息不能为空！")
        return

    # 数据库操作：新增/更新账户
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

# 3. 删除账户 (/delete 标题)
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

    # 先检查账户是否存在
    c.execute("SELECT 1 FROM accounts WHERE title=?", (title,))
    if not c.fetchone():
        conn.close()
        update.message.reply_text(f"❌ 账户「{title}」不存在！")
        return

    # 级联删除：先删历史记录，再删账户（也可设置SQLite外键级联，这里手动删更清晰）
    c.execute("DELETE FROM account_history WHERE title=?", (title,))
    c.execute("DELETE FROM accounts WHERE title=?", (title,))

    conn.commit()
    conn.close()
    update.message.reply_text(f"✅ 账户「{title}」已删除（含历史记录）！")


# 4. 列出所有账户 (/list)
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


# 5. 添加管理员 (/addadmin 用户ID)
def add_admin(update: Update, context: CallbackContext):
    # 仅超级管理员（创建者）可添加管理员
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


# 6. 移除管理员 (/removeadmin 管理员ID)
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


# 7. 查看管理员列表 (/admins)
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


# 8. 查看账户历史记录 (/history 标题)
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

    # 先检查账户是否存在
    c.execute("SELECT 1 FROM accounts WHERE title=?", (title,))
    if not c.fetchone():
        conn.close()
        update.message.reply_text(f"❌ 账户「{title}」不存在！")
        return

    # 倒序查询历史记录（最新的在前）
    c.execute('''SELECT content, create_time FROM account_history 
                 WHERE title=? ORDER BY create_time DESC''', (title,))
    history = c.fetchall()
    conn.close()

    if not history:
        update.message.reply_text(f"📜 账户「{title}」暂无历史记录！")
        return

    # 拼接历史记录（带时间戳）
    history_text = f"📜 账户「{title}」历史记录（倒序）：\n"
    for idx, (content, create_time) in enumerate(history, 1):
        history_text += f"\n{idx}. 记录时间：{create_time}\n内容：{content}\n"
    update.message.reply_text(history_text)


# 9. 群聊@机器人查询账户信息（标题 @Abc_account_bot）
def query_account(update: Update, context: CallbackContext):
    message = update.message.text
    bot_username = context.bot.username  # 机器人的用户名（Abc_account_bot）

    # 仅处理包含@机器人的消息
    if f"@{bot_username}" not in message:
        return

    # 解析标题（@前的内容，去除空格）
    title = message.split(f"@{bot_username}")[0].strip()
    if not title:
        update.message.reply_text("❌ 格式错误！正确格式：账户标题 @Abc_account_bot")
        return

    # 查询账户当前内容
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT current_content FROM accounts WHERE title=?", (title,))
    content = c.fetchone()
    conn.close()

    if content:
        update.message.reply_text(f"📋 账户「{title}」的信息：\n{content[0]}")
    else:
        update.message.reply_text(f"❌ 账户「{title}」不存在！")


# -------------------------- 机器人启动入口 --------------------------
def main():
    # 初始化数据库（首次运行自动创建表）
    init_db()

    # 创建Updater和Dispatcher（核心调度器）
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher

    # 注册所有命令处理器
    dp.add_handler(CommandHandler("myid", myid))
    dp.add_handler(CommandHandler("add", add_account))
    dp.add_handler(CommandHandler("delete", delete_account))
    dp.add_handler(CommandHandler("list", list_accounts))
    dp.add_handler(CommandHandler("addadmin", add_admin))
    dp.add_handler(CommandHandler("removeadmin", remove_admin))
    dp.add_handler(CommandHandler("admins", list_admins))
    dp.add_handler(CommandHandler("history", view_history))

    # 注册消息处理器（监听群聊@机器人的消息）
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, query_account))

    # 启动机器人（持续运行）
    print("机器人已启动，按Ctrl+C停止...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()