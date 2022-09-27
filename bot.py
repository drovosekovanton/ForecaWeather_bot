import telebot
from bs4 import BeautifulSoup
from requests import get, exceptions
from custom_token import TOKEN


# http://t.me/ForecaWeather_bot

THIS_DAY_URL = 'https://www.foreca.com/ru/100561347/Glazov-Udmurtiya-Republic-Russia/hourly?day=0'
NEXT_DAY_URL = 'https://www.foreca.com/ru/100561347/Glazov-Udmurtiya-Republic-Russia/hourly?day=1'
TEN_DAY_URL = 'https://www.foreca.com/ru/100561347/Glazov-Udmurtiya-Republic-Russia/10-day-forecast'

# wind_dict = {
#     'N': '\u2193',  # ↓
#     'NE': '\u2199',  # ↙
#     'E': '\u2190',  # ←
#     'SE': '\u2196',  # ↖
#     'S': '\u2191',  # ↑
#     'SW': '\u2197',  # ↗
#     'W': '\u2192',  # →
#     'NW': '\u2198',  # ↘
# }

# wind_dict = {  # arrow emojis from unicode table
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

    def hour_fetcher(url) -> str:
        request_result = None
        try:
            request_result = get(url)
        except exceptions.ConnectionError:
            pass
        finally:
            if request_result is None or request_result.status_code != 200:
                return 'Weather forecast is not available now'

        soup = BeautifulSoup(request_result.text, 'html.parser')
        day = soup.find_all(class_='hour')
        forecast = []
        for hour_row in day:
            time = hour_row.find(class_='value time time_24h').text
            temperature = (
                    hour_row.find(class_='value temp temp_c warm') or
                    hour_row.find(class_='value temp temp_c cold')).text
            temperature_feel = hour_row.find(class_='value temp temp_c').text
            precipitation = list(hour_row.find(class_='value rain rain_mm').stripped_strings)[0]  # w/o units
            wind_name = hour_row.find(class_='wind').find('img').attrs['alt']
            wind_dir = wind_dict.get(wind_name, 'Ø')
            wind_speed = hour_row.find(class_='value wind wind_ms').text
            row_str = f'{time:>3}|{temperature:>3}|{temperature_feel:>4}|{precipitation:>4}|{wind_speed:>2}{wind_dir}'
            forecast.append(row_str)
        return ''.join(
            [
                '```\n',
                'час|тмп|ощущ|осад|втр\n',
                '---+---+----+----+---\n',
                # ' 22| +9|  +7| 0.1| 4 =>',
                '\n'.join(forecast),
                '```',
            ]
        )

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
                return 'Weather forecast is not available now'

        soup = BeautifulSoup(request_result.text, 'html.parser')
        days = soup.find_all(class_='day')
        forecast = []
        for day in days:
            date = day.find(class_='date').text
            temperatures = day.find_all(class_='value temp temp_c')
            # remove Celsius sign, else use temp_max, temp_min
            temp_max, temp_min = temperatures[0].text[:-1], temperatures[1].text[:-1]
            precipitation = ''.join(
                day.find(class_='value rain rain_mm').text.split()[:-1]  # w/o units, may be as "< 0.1 mm"
            )
            wind = day.find(class_='value wind wind_ms').text
            row_str = f'{date:>5}|{temp_max:>4}|{temp_min:>4}|{precipitation:>5}|{wind:>3}'
            forecast.append(row_str)

        return ''.join(
            [
                '```\n',
                ' дата|макс| мин| осад|втр\n',
                '-----+----+----+-----+---\n',
                '\n'.join(forecast),
                '```',
            ]
        )

    def get_help() -> str:
        return 'Жми кнопец на клавиатуре бота, тут сложно ошибиться'

    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, 'Давайте начнём!', reply_markup=markup)

    @bot.message_handler(commands=['stop'])
    def start(message):
        bot.send_message(message.chat.id, 'Пока!')
        bot.stop_bot()

    @bot.message_handler(commands=['help'])
    def help_bot(message):
        bot.send_message(message.chat.id, get_help())

    func_map = {
        'эти сутки': hours,
        'следующие сутки': next_day,
        '10 дней': week,
        'справка': get_help,
    }

    # define keyboard
    markup = telebot.types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    menu_buttons = []
    for b in func_map:
        menu_buttons.append(telebot.types.KeyboardButton(b.capitalize()))
    markup.add(*menu_buttons)

    @bot.message_handler(
        func=lambda m: m.text.lower() in [str(e).lower() for e in func_map],
        content_types=['text'],
    )
    def any_text(message):
        message_ = func_map[message.text.lower()]()
        bot.send_message(message.chat.id, message_, reply_markup=markup, parse_mode='MarkdownV2')

    # run bot
    bot.infinity_polling()


if __name__ == '__main__':
    run()
