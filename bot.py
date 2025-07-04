import json
import logging
import re
import telebot
import cloudscraper

from bs4 import BeautifulSoup
from requests import exceptions
from datetime import datetime, timedelta
from collections import defaultdict

from config import TOKEN, ADMINS

THIS_DAY_URL = 'https://www.foreca.com/ru/100561347/Glazov-Udmurtiya-Republic-Russia/hourly?day=0'
NEXT_DAY_URL = 'https://www.foreca.com/ru/100561347/Glazov-Udmurtiya-Republic-Russia/hourly?day=1'
TEN_DAY_URL = 'https://www.foreca.com/ru/100561347/Glazov-Udmurtiya-Republic-Russia/10-day-forecast'

# wind_dict = {  # ugly output
#     'N': '\u2193',  # ↓
#     'NE': '\u2199',  # ↙
#     'E': '\u2190',  # ←
#     'SE': '\u2196',  # ↖
#     'S': '\u2191',  # ↑
#     'SW': '\u2197',  # ↗
#     'W': '\u2192',  # →
#     'NW': '\u2198',  # ↘
# }

# wind_dict = {  # arrow emojis from Unicode table, ugly output too
#     'N': '\u2b07',  # ↓
#     'NE': '\u2199',  # ↙
#     'E': '\u2b05',  # ←
#     'SE': '\u2196',  # ↖
#     'S': '\u2b06',  # ↑
#     'SW': '\u2197',  # ↗
#     'W': '\u27a1',  # →
#     'NW': '\u2198',  # ↘
# }

WIND_DICT = {  # double arrow emojis from Unicode table
    'N': '\u21d3',  # ↓
    'NE': '\u21d9',  # ↙
    'E': '\u21d0',  # ←
    'SE': '\u21d6',  # ↖
    'S': '\u21d1',  # ↑
    'SW': '\u21d7',  # ↗
    'W': '\u21d2',  # →
    'NW': '\u21d8',  # ↘
}

# Cooldown in seconds
COOLDOWN = 5


def run():
    bot = telebot.TeleBot(TOKEN)
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    last_user_action = defaultdict(lambda: datetime.min)

    # warm-up with cloudscraper to get cookies, etc.
    # using it as a persistent session
    scraper = cloudscraper.create_scraper()
    scraper.get("https://www.foreca.com", timeout=10)
    logging.info("Scraper started")

    def log(message: telebot.types.Message):
        # log request string and username, just in case
        logging.info(f'Request \'{message.text}\' from \'{message.chat.username}\' ({message.from_user.id})')

    def hour_fetcher(url: str) -> str:
        # values extracted from data field of some js script
        request_result = None
        try:
            request_result = scraper.get(url, timeout=(5, 5))
        except exceptions.ConnectionError:
            pass
        finally:
            if request_result is None or request_result.status_code != 200:
                return 'Прогноз погоды сейчас по какой-то причине недоступен'

        soup = BeautifulSoup(request_result.text, 'html.parser')
        forecast = []
        # Find the <script> tags and extract JavaScript code
        scripts = soup.find_all('script')
        js_code = ''
        for script in scripts:
            if script.get_text():
                js_code += script.get_text()
        # extract data field with all the values formatted in JSON
        pattern = re.compile(r'data: (\[\{.*}])', re.DOTALL)
        try:
            hour_data = json.loads(pattern.search(js_code).group(1))
        except json.decoder.JSONDecodeError:
            return 'Ошибка в извлечении данных с сайта'
        if hour_data is None:
            return 'С сайта возвращены пустые данные'

        for hour in hour_data:
            time = hour["h24"]
            temperature = hour["temp"]
            temperature_feel = hour["flike"]
            precipitation = hour["rain"]
            wind_dir = WIND_DICT.get(hour["windCardinal"], 'Ø')
            wind_speed = hour["winds"]
            row_str = f'{time:>3}|{temperature:>3}|{temperature_feel:>4}|{round(float(precipitation), 1):>4g}|{wind_speed:>2}{wind_dir}'
            forecast.append(row_str)
        return ''.join(['```\n',
                        'час|тмп|ощущ|осад|втр\n',
                        '---+---+----+----+---\n',
                        # ' 22| +9|  +7| 0.1| 4 =>',
                        '\n'.join(forecast),
                        '```', ])

    def hours() -> str:
        return hour_fetcher(THIS_DAY_URL)

    def next_day() -> str:
        return hour_fetcher(NEXT_DAY_URL)

    def week() -> str:
        # since html prefilled with data on server side, extract values from corresponding divs
        request_result = None
        try:
            request_result = scraper.get(TEN_DAY_URL, timeout=(5, 5))
        except exceptions.ConnectionError:
            pass
        finally:
            if request_result is None or request_result.status_code != 200:
                return 'Прогноз погоды сейчас по какой-то причине недоступен'

        soup = BeautifulSoup(request_result.text, 'html.parser')
        forecast = []
        for day in soup.find_all(class_='day-container'):
            date = day.find_next(class_='date').get_text()
            # current day's max and min, 'value temp temp_c max' and 'value temp temp_c'
            temperatures = day.find_all_next(class_=re.compile('value temp temp_c'), limit=2)
            # remove Celsius sign from temps, strings look like '+23°'
            temp_max, temp_min = temperatures[0].get_text()[:-1], temperatures[1].get_text()[:-1]
            # strip off units and spaces from precip, it can contain additional sign
            # string looks like '< 0.1 mm' or '2.4 mm'
            precipitation = ''.join(day.find_next(class_='value rain rain_mm').get_text().split()[:-1])
            wind_speed = ''.join(day.find_next(class_='value wind wind_ms').get_text().split()[:-1])
            # get wind direction from 'alt' attribute of wind picture, it's an abbreviation like W, NE
            # we use some beautifulsoup4 magic here to find 'alt' attribute from 'img' tag
            # noinspection PyUnresolvedReferences
            wind_name = day.find_next(class_='wind').img['alt']
            wind_dir = WIND_DICT.get(wind_name, 'Ø')
            row_str = f'{date:>6}|{temp_max:>4}|{temp_min:>4}|{precipitation:>5}|{wind_speed:>2}{wind_dir}'
            forecast.append(row_str)
        return ''.join(['```\n',
                        '  дата|макс| мин| осад|втр\n',
                        '------+----+----+-----+---\n',
                        '\n'.join(forecast),
                        '```', ])

    def get_help() -> str:
        # Character '.' is reserved and must be escaped with the preceding '\'
        return ('Запрос прогноза погоды для одного очень хорошего города\\.\n'
                'Жми кнопку на клавиатуре бота, тут сложно ошибиться')

    @bot.message_handler(commands=['start'])
    def start(message: telebot.types.Message):
        log(message)
        bot.send_message(message.chat.id, 'Давайте начнём!', reply_markup=markup)

    @bot.message_handler(commands=['stop'])
    def stop(message: telebot.types.Message):
        log(message)
        bot.send_message(message.chat.id, 'Пока!')
        bot.stop_bot()

    @bot.message_handler(commands=['help'])
    def help_bot(message: telebot.types.Message):
        log(message)
        bot.send_message(message.chat.id, get_help())

    # keys are used for buttons and filtering input
    # values are for corresponding action
    func_map = {key.lower(): value for key, value in
                {
                    'эти сутки': hours,
                    'следующие сутки': next_day,
                    '10 дней': week,
                    'справка': get_help,
                }.items()
                }

    # define keyboard
    markup = telebot.types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    menu_buttons = []
    for b in func_map:
        menu_buttons.append(telebot.types.KeyboardButton(b.capitalize()))
    markup.add(*menu_buttons)

    @bot.message_handler(func=lambda m: m.text.lower() in [str(e) for e in func_map], content_types=['text'], )
    def any_text(message: telebot.types.Message):
        log(message)
        user_id = message.from_user.id
        now = datetime.now()

        # Skip cooldown check for admins
        if user_id not in ADMINS:
            if now - last_user_action[user_id] < timedelta(seconds=COOLDOWN):
                bot.send_message(message.chat.id, f'Подожди немного, не так быстро 🕒 (лимит {COOLDOWN} сек)',
                                 reply_markup=markup)
                return
            last_user_action[user_id] = now

        message_ = func_map[message.text.lower()]()
        bot.send_message(message.chat.id, message_, reply_markup=markup, parse_mode='MarkdownV2')

    # run bot
    bot.infinity_polling(timeout=10, long_polling_timeout=5)


if __name__ == '__main__':
    run()
