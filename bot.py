import telebot
from telebot import types
import sqlite3
import threading
import time

bot = telebot.TeleBot('6545028418:AAGnGbeAk7SJ1oGow7VGxb8XP72dCHx6nxI')
admins = ["1264085527", "1313197485"]

# Опросы
created_polls = {}
sessions = {}
user_balances = {}
question_list = []
questions = {}
answers_status = []
current_poll_name = None  # Храним название текущего опроса, который создается

# Пример товаров в магазине
shop_items = {
    "Товар 1": {"price": 100, "description": "Описание товара 1"},
    "Товар 2": {"price": 150, "description": "Описание товара 2"},
    "Товар 3": {"price": 200, "description": "Описание товара 3"}
}


# Инициализация базы данных
def open_connect_db():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    return connection, cursor


def close_connect_db(connection):
    connection.close()


def create_table(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS Users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        age INTEGER,
        pol TEXT,
        balance INTEGER DEFAULT 0,
        referrer_id INTEGER,
        referral_link TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS Polls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        questions TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS PollResults (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        poll_name TEXT,
        question TEXT,
        answer TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS BotStats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        event TEXT,
        user_id INTEGER,
        poll_name TEXT,
        question TEXT,
        answer TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS PollReviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        poll_name TEXT,
        user_id INTEGER,
        review TEXT
    )''')


def connect_commit(connection):
    connection.commit()


def db_execute(cursor, telegram_id, age=None, pol=None):
    cursor.execute(
        'INSERT OR IGNORE INTO Users (telegram_id, age, pol) VALUES (?, ?, ?)',
        (telegram_id, age if age is not None else 0, pol if pol is not None else "None")
    )


def execute_query(query):
    connection, cursor = open_connect_db()
    cursor.execute(query)
    connection.commit()
    close_connect_db(connection)


def check_user_exists(telegram_id):
    connection, cursor = open_connect_db()
    cursor.execute('SELECT * FROM Users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    close_connect_db(connection)
    return user is not None


connection, cursor = open_connect_db()
create_table(cursor)
connect_commit(connection)
close_connect_db(connection)


# Загрузка опросов из базы данных
def load_polls():
    connection, cursor = open_connect_db()
    cursor.execute("SELECT name, questions FROM Polls")
    rows = cursor.fetchall()
    for row in rows:
        poll_name = row[0]
        questions_str = row[1]
        questions = questions_str.split('%')  # Разделяем вопросы по символу %
        created_polls[poll_name] = {
            'questions': questions,
            'current_question_index': 0,
            'responses': []
        }
    close_connect_db(connection)


# Сохранение опроса в базу данных
def save_poll_to_db(poll_name, questions_str):
    connection, cursor = open_connect_db()
    cursor.execute(
        'INSERT OR IGNORE INTO Polls (name, questions) VALUES (?, ?)',
        (poll_name, questions_str)
    )
    connection.commit()
    close_connect_db(connection)


@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if user_id not in user_balances:
        user_balance = get_user_balance(user_id)
        user_balances[user_id] = user_balance
    else:
        user_balance = user_balances[user_id]

    markup = types.InlineKeyboardMarkup()
    if str(user_id) in admins:
        add_poll_button = types.InlineKeyboardButton("Добавить опрос", callback_data="add_poll")
        markup.add(add_poll_button)

    choose_poll_button = types.InlineKeyboardButton("Выбор опроса", callback_data="choose_poll")
    shop_button = types.InlineKeyboardButton("Магазин", callback_data="shop")
    balance_button = types.InlineKeyboardButton(f"Баланс: {user_balance} блалов", callback_data="balance")
    markup.add(choose_poll_button, shop_button, balance_button)

    referral_link = get_referral_link(user_id)
    if referral_link:
        markup.add(types.InlineKeyboardButton("Моя реферальная ссылка", url=referral_link))

    # Кнопка "Получить реферальную ссылку"
    get_referral_link_button = types.InlineKeyboardButton("Получить реферальную ссылку",
                                                          callback_data="get_referral_link")
    markup.add(get_referral_link_button)

    bot.send_sticker(message.chat.id, 'CAACAgIAAxkBAAENDlNnJUI9BowHaNS9n0cgTIYJULWt6wACYggAAowt_QcxfmppHBvPaTYE')
    bot.send_message(message.chat.id, "Добро пожаловать! Выберите опцию ниже.", reply_markup=markup)
    save_bot_stats('start', user_id)


@bot.callback_query_handler(func=lambda call: call.data == "choose_poll")
def choose_poll(call):
    markup = types.InlineKeyboardMarkup()
    for poll_name in created_polls.keys():
        markup.add(types.InlineKeyboardButton(poll_name, callback_data=f'start_poll_{poll_name}'))

    markup.add(types.InlineKeyboardButton("Вернуться назад", callback_data="back_to_menu"))
    bot.send_message(call.message.chat.id, "Выберите опрос:", reply_markup=markup)
    bot.delete_message(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('start_poll_'))
def start_poll(call):
    global current_poll_name, answers_status
    poll_name = call.data.split('_')[2]
    current_poll_name = poll_name
    user_id = call.from_user.id

    if poll_name in created_polls:
        created_polls[poll_name]['current_question_index'] = 0
        created_polls[poll_name]['responses'] = []
        answers_status.clear()
        answers_status = [" "] * len(created_polls[poll_name]['questions'])

        send_question(call.message.chat.id, poll_name)
        bot.delete_message(call.message.chat.id, call.message.message_id)

        add_user_balance(user_id, 100)
        user_balances[user_id] += 100
        bot.send_message(call.message.chat.id, "Вам начислено 100 блалов за прохождение опроса!")

        # Даем реферальному бонусу
        referrer_id = get_referrer_id(user_id)
        if referrer_id:
            add_user_balance(referrer_id, 50)
            user_balances[referrer_id] += 50
            bot.send_message(referrer_id, f"Вам начислено 50 блалов за реферала!")
    else:
        bot.send_message(call.message.chat.id, "Опрос не найден.")


def send_question(chat_id, poll_name):
    questions = created_polls[poll_name]['questions']
    current_question_index = created_polls[poll_name]['current_question_index']
    responses = created_polls[poll_name]['responses']

    if current_question_index < len(questions):
        question = questions[current_question_index]

        question_parts = question.split(":")
        question_text = question_parts[0].strip()
        answers = question_parts[1].split(',')

        markup = types.InlineKeyboardMarkup()
        for answer in answers:
            markup.add(types.InlineKeyboardButton(answer.strip(),
                                                  callback_data=f'answer_{current_question_index}_{answer.strip()}'))

        status_message = "".join(f"{answers_status[i]} " for i in range(len(answers_status)))
        question_counter = f"{current_question_index + 1}/{len(questions)}"
        bot.send_message(chat_id, f"{status_message} {question_counter}\n{question_text}", reply_markup=markup)

    else:
        bot.send_message(chat_id, "Спасибо за участие в опросе!")


@bot.callback_query_handler(func=lambda call: call.data.startswith('answer_'))
def handle_answer(call):
    _, question_index, answer = call.data.split('_')
    question_index = int(question_index)
    poll_name = current_poll_name
    user_id = call.from_user.id

    created_polls[poll_name]['responses'].append(answer)
    answers_status[question_index] = " "
    created_polls[poll_name]['current_question_index'] += 1

    save_bot_stats('answer', call.from_user.id, poll_name, created_polls[poll_name]['questions'][question_index],
                   answer)
    save_poll_result(user_id, poll_name, created_polls[poll_name]['questions'][question_index], answer)

    if created_polls[poll_name]['current_question_index'] < len(answers_status):
        send_question(call.message.chat.id, poll_name)
    else:
        markup = types.InlineKeyboardMarkup()
        link_button = types.InlineKeyboardButton("Telegram канал", url="https://t.me/sberbank/")
        start_button = types.InlineKeyboardButton("Отзывы", callback_data="review")
        back_button = types.InlineKeyboardButton("Вернуться назад", callback_data="back_to_menu")
        markup.add(link_button, start_button, back_button)
        bot.send_message(call.message.chat.id,
                         "Спасибо за участие в опросе! Можете подписаться на наш Telegram канал и оставить отзыв об опросе.",
                         reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_menu')
def back_to_menu(call):
    user_id = call.message.from_user.id
    markup = types.InlineKeyboardMarkup()
    if str(user_id) in admins:
        add_poll_button = types.InlineKeyboardButton("Добавить опрос", callback_data="add_poll")
        markup.add(add_poll_button)

    choose_poll_button = types.InlineKeyboardButton("Выбор опроса", callback_data="choose_poll")
    shop_button = types.InlineKeyboardButton("Магазин", callback_data="shop")
    try:
        num = user_balances[call.message.from_user.id]
    except:
        num = 0
    balance_button = types.InlineKeyboardButton(f"Баланс: {num} блалов", callback_data="balance")
    markup.add(choose_poll_button, shop_button, balance_button)

    referral_link = get_referral_link(user_id)
    if referral_link:
        markup.add(types.InlineKeyboardButton("Моя реферальная ссылка", url=referral_link))

    get_referral_link_button = types.InlineKeyboardButton("Получить реферальную ссылку",
                                                          callback_data="get_referral_link")
    markup.add(get_referral_link_button)

    bot.send_message(call.message.chat.id, "Вы вернулись в меню.", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "shop")
def shop(call):
    markup = types.InlineKeyboardMarkup()
    for item_name, item_info in shop_items.items():
        markup.add(
            types.InlineKeyboardButton(f"{item_name} - {item_info['price']} блалов", callback_data=f'buy_{item_name}'))

    back_button = types.InlineKeyboardButton("Назад", callback_data="back_to_menu")
    markup.add(back_button)
    bot.send_message(call.message.chat.id, "Добро пожаловать в магазин! Выберите товар:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_item(call):
    user_id = call.from_user.id
    item_name = call.data.split("_")[1]

    if item_name in shop_items:
        item_price = shop_items[item_name]["price"]
        if user_balances[user_id] >= item_price:
            user_balances[user_id] -= item_price
            bot.send_message(call.message.chat.id, f"Вы купили {item_name}!")
            save_purchase(user_id, item_name)
        else:
            bot.send_message(call.message.chat.id, "У вас недостаточно блалов для покупки этого товара.")
    else:
        bot.send_message(call.message.chat.id, "Товар не найден.")


def save_purchase(user_id, item_name):
    connection, cursor = open_connect_db()
    cursor.execute(
        'INSERT INTO Purchases (user_id, item_name) VALUES (?, ?)',
        (user_id, item_name)
    )
    connection.commit()
    close_connect_db(connection)


def get_user_balance(user_id):
    connection, cursor = open_connect_db()
    cursor.execute('SELECT balance FROM Users WHERE telegram_id = ?', (user_id,))
    balance = cursor.fetchone()
    close_connect_db(connection)
    return balance[0] if balance else 0


def add_user_balance(user_id, amount):
    connection, cursor = open_connect_db()
    cursor.execute('UPDATE Users SET balance = balance + ? WHERE telegram_id = ?', (amount, user_id))
    connection.commit()
    close_connect_db(connection)


def save_poll_result(user_id, poll_name, question, answer):
    connection, cursor = open_connect_db()
    cursor.execute(
        'INSERT INTO PollResults (telegram_id, poll_name, question, answer) VALUES (?, ?, ?, ?)',
        (user_id, poll_name, question, answer)
    )
    connection.commit()
    close_connect_db(connection)


def save_bot_stats(event, user_id, poll_name=None, question=None, answer=None):
    connection, cursor = open_connect_db()
    cursor.execute(
        'INSERT INTO BotStats (event, user_id, poll_name, question, answer) VALUES (?, ?, ?, ?, ?)',
        (event, user_id, poll_name, question, answer)
    )
    connection.commit()
    close_connect_db(connection)


@bot.callback_query_handler(func=lambda call: call.data == "review")
def handle_review(call):
    user_id = call.from_user.id
    poll_name = current_poll_name

    bot.send_message(call.message.chat.id, "Напишите ваш отзыв об опросе:")
    bot.register_next_step_handler(call.message, process_review, user_id, poll_name)


def process_review(message, user_id, poll_name):
    review_text = message.text
    save_review(user_id, poll_name, review_text)
    bot.send_message(message.chat.id, "Спасибо за ваш отзыв!")


def save_review(user_id, poll_name, review_text):
    connection, cursor = open_connect_db()
    cursor.execute(
        'INSERT INTO PollReviews (poll_name, user_id, review) VALUES (?, ?, ?)',
        (poll_name, user_id, review_text)
    )
    connection.commit()
    close_connect_db(connection)


# Реферальная система
def get_referral_link(user_id):
    connection, cursor = open_connect_db()
    cursor.execute('SELECT referral_link FROM Users WHERE telegram_id = ?', (user_id,))
    link = cursor.fetchone()
    close_connect_db(connection)
    return link[0] if link else None


def generate_referral_link(user_id):
    referral_link = f'https://t.me/Neumarkbot?start=ref_{user_id}'  # Замените your_bot_username на имя вашего бота
    connection, cursor = open_connect_db()
    cursor.execute('UPDATE Users SET referral_link = ? WHERE telegram_id = ?', (referral_link, user_id))
    connection.commit()
    close_connect_db(connection)
    return referral_link


def get_referrer_id(user_id):
    connection, cursor = open_connect_db()
    cursor.execute('SELECT referrer_id FROM Users WHERE telegram_id = ?', (user_id,))
    referrer_id = cursor.fetchone()
    close_connect_db(connection)
    return referrer_id[0] if referrer_id else None


@bot.message_handler(func=lambda message: message.text.startswith('/start ref_'))
def handle_referral(message):
    referral_code = message.text.split(' ')[1]
    referrer_id = int(referral_code.split('_')[1])
    user_id = message.from_user.id

    if not check_user_exists(user_id):
        connection, cursor = open_connect_db()
        cursor.execute('INSERT INTO Users (telegram_id, referrer_id) VALUES (?, ?)', (user_id, referrer_id))
        connection.commit()
        close_connect_db(connection)

        bot.send_message(message.chat.id, "Вы успешно зарегистрированы по реферальной ссылке!")
        generate_referral_link(user_id)

        # Даем рефералу 50 баллов
        add_user_balance(referrer_id, 50)
        user_balances[referrer_id] += 50
        bot.send_message(referrer_id, f"Вам начислено 50 блалов за реферала!")


@bot.callback_query_handler(func=lambda call: call.data == "get_referral_link")
def handle_get_referral_link(call):
    user_id = call.from_user.id
    referral_link = generate_referral_link(user_id)
    bot.send_message(call.message.chat.id, f"Ваша реферальная ссылка: {referral_link}")


# Запуск бота
load_polls()
bot.polling(none_stop=True)