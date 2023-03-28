import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import StatusCodeError


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_TOKEN')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

env_tokens = {
    PRACTICUM_TOKEN: 'токен Яндекс Практикум',
    TELEGRAM_TOKEN: 'токен Телеграм бота',
    TELEGRAM_CHAT_ID: 'идентификатор Телеграм чата'
}


def check_tokens():
    """
    Проверка наличия токенов.
    При отсутсвии нужного токена выводит ошибку в терминал и
    выбрасывает исключение.
    """

    def get_description():
        """Возвращает описание токена."""
        for token, description in env_tokens.items():
            if token is None:
                return description

    if (PRACTICUM_TOKEN is None
            or TELEGRAM_TOKEN is None
            or TELEGRAM_CHAT_ID is None):
        logging.critical(
            f'Ошибка при обработке токенов. Убедитесь,'
            f' что указан {get_description()}!'
        )
        sys.exit(1)


def send_message(bot, message):
    """
    Отправляет сообщение по заданному идентификатору чата.
    В случае ошибки при отправке выбрасывает исключение.
    """
    logging.debug('Начало отправки сообщения...')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение <<{message}>> успешно отправлено')
    except telegram.TelegramError as e:
        logging.error(f'Возникла ошибка при отправке сообщения: {e}')


def get_api_answer(timestamp):
    """Делает запрос к API Практикума."""
    params = {'from_date': timestamp}
    logging.debug('Отправлен запрос к API Яндекс по '
                  f'адресу {ENDPOINT} с параметрами: {params}')
    try:
        api_answer = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as e:
        raise ConnectionError(
            f'Ошибка при попытке подключении к API Яндекса: {e}'
            f' по адресу {ENDPOINT} c параметами {params}'
        )
    if api_answer.status_code != requests.codes.OK:
        raise StatusCodeError(
            'API Яндекса вернул код статуса отличный'
            f' от 200: {api_answer.status_code}.'
        )
    logging.debug('Запрос к API Яндекс прошел успешно.')
    return api_answer.json()


def check_response(response):
    """
    Делает проверки ответа от API.
    В случае несовпадения структуры ответа с ожидаемым
    выкидывает исключения.
    """
    logging.debug('Начало проверки ответа от сервера...')
    if not isinstance(response, dict):
        raise TypeError('Ответ API Яндекса пришел не в виде словаря')
    if response.get('current_date') is None:
        raise KeyError('Ответ API Яндекса пришел без ключа current_date')
    if response.get('homeworks') is None:
        raise KeyError('Ответ API Яндекса пришел без ключа homeworks')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('homeworks в ответе API не является списком')
    logging.debug('Проверка ответа успешно завершена')


def parse_status(homework):
    """Проверяет статус домашней работы."""
    logging.debug('Начало проверки статуса домашней работы...')
    if 'homework_name' not in homework:
        raise KeyError(
            'В ответе API домашней работы отсутствует ключ homework_name'
        )
    if 'status' not in homework:
        raise KeyError(
            'В ответе API домашней работы отсутствует ключ status'
        )
    homework_name = homework['homework_name']
    for name, verdict in HOMEWORK_VERDICTS.items():
        if homework['status'] not in HOMEWORK_VERDICTS.keys():
            raise ValueError(
                'Статус домашней работы отсутствует или незадокументирован'
            )
        if name == homework['status']:
            return (f'Изменился статус проверки работы'
                    f' "{homework_name}". {verdict}')


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            timestamp = response['current_date']
            if response['homeworks']:
                homework = response.get('homeworks')
                send_message(bot, parse_status(homework[0]))
                last_error = None
            else:
                logging.debug('Статус домашней работы не изменился.')

        except Exception as error:
            if last_error != error:
                message = f'Сбой в работе программы: {error}'
                logging.error(message, exc_info=True)
                send_message(bot, message)
                last_error = error

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':

    logging.basicConfig(
        format=(
            '%(asctime)s - %(lineno)d - %(name)s - '
            '%(funcName)s - %(levelname)s - %(message)s'
        ),
        level=logging.DEBUG,
        stream=sys.stdout
    )

    main()
