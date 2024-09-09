import telebot
from bs4 import BeautifulSoup
from requests import get, exceptions
from custom_token import TOKEN

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

wind_dict = {  # double arrow emojis from unicode table
    'N': '\u21d3',  # ↓
    'NE': '\u21d9',  # ↙
    'E': '\u21d0',  # ←
    'SE': '\u21d6',  # ↖
    'S': '\u21d1',  # ↑
    'SW': '\u21d7',  # ↗
    'W': '\u21d2',  # →
    'NW': '\u21d8',  # ↘
}


def run():
    bot = telebot.TeleBot(TOKEN)

    def log(message: telebot.types.Message):
        # log request string and username, just in case
        print(f'Request \'{message.text}\' from \'{message.chat.username}\'')

    def hour_fetcher(url: str) -> str:
        request_result = None
        try:
            request_result = get(url)
        except exceptions.ConnectionError:
            pass
        finally:
            if request_result is None or request_result.status_code != 200:
                return 'Прогноз погоды сейчас по какой-то причине недоступен'

        soup = BeautifulSoup(request_result.text, 'html.parser')
        forecast = []
        for hour_row in soup.find_all(class_='hour'):
            time = hour_row.find_next(class_='value time time_24h').get_text()
            temperature = (hour_row.find_next(class_='value temp temp_c warm') or hour_row.find_next(
                class_='value temp temp_c cold')).get_text()
            temperature_feel = hour_row.find_next(class_='value temp temp_c').get_text()
            precipitation = list(hour_row.find_next(class_='value rain rain_mm').stripped_strings)[0]  # w/o units
            # get wind direction from 'alt' attribute of wind picture, it's an abbreviation like W, NE
            # we use some beautifulsoup4 magic here to find 'alt' attribute from 'img' tag
            # noinspection PyUnresolvedReferences
            wind_name = hour_row.find_next(class_='wind').img['alt']
            wind_dir = wind_dict.get(wind_name, 'Ø')
            wind_speed = hour_row.find_next(class_='value wind wind_ms').get_text()
            row_str = f'{time:>3}|{temperature:>3}|{temperature_feel:>4}|{precipitation:>4}|{wind_speed:>2}{wind_dir}'
            forecast.append(row_str)
        return ''.join(['```\n', 'час|тмп|ощущ|осад|втр\n', '---+---+----+----+---\n',  # ' 22| +9|  +7| 0.1| 4 =>',
                        '\n'.join(forecast), '```', ])

    def hours() -> str:
        return hour_fetcher(THIS_DAY_URL)

    def next_day() -> str:
        return hour_fetcher(NEXT_DAY_URL)

    def week() -> str:
        request_result = None
        try:
            request_result = get(TEN_DAY_URL)
        except exceptions.ConnectionError:
            pass
        finally:
            if request_result is None or request_result.status_code != 200:
                return 'Прогноз погоды сейчас по какой-то причине недоступен'

        soup = BeautifulSoup(request_result.text, 'html.parser')
        forecast = []
        for day in soup.find_all(class_='day'):
            date = day.find_next(class_='date').get_text()
            # current day's max and min
            temperatures = day.find_all_next(class_='value temp temp_c', limit=2)
            # remove Celsius sign from temps, input may be '+23°'
            temp_max, temp_min = temperatures[0].get_text()[:-1], temperatures[1].get_text()[:-1]
            # strip off units and spaces from precip, input may be '< 0.1 mm' or '2.4 mm'
            precipitation = ''.join(day.find_next(class_='value rain rain_mm').get_text().split()[:-1])
            wind_speed = day.find_next(class_='value wind wind_ms').get_text()
            # get wind direction from 'alt' attribute of wind picture, it's an abbreviation like W, NE
            # we use some beautifulsoup4 magic here to find 'alt' attribute from 'img' tag
            # noinspection PyUnresolvedReferences
            wind_name = day.find_next(class_='wind').img['alt']
            wind_dir = wind_dict.get(wind_name, 'Ø')
            row_str = f'{date:>5}|{temp_max:>4}|{temp_min:>4}|{precipitation:>5}|{wind_speed:>2}{wind_dir}'
            forecast.append(row_str)

        return ''.join(
            ['```\n', ' дата|макс| мин| осад|втр\n', '-----+----+----+-----+---\n', '\n'.join(forecast), '```', ])

    def get_help() -> str:
        # '.' is a reserved symbol and must be escaped
        return ('Запрос прогноза погоды для одного очень хорошего города\.\n' +
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

    @bot.message_handler(func=lambda m: m.text.lower() in [str(e).lower() for e in func_map], content_types=['text'], )
    def any_text(message: telebot.types.Message):
        log(message)
        message_ = func_map[message.text.lower()]()
        bot.send_message(message.chat.id, message_, reply_markup=markup, parse_mode='MarkdownV2')

    # run bot
    bot.infinity_polling()


if __name__ == '__main__':
    run()
