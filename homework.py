import logging
import os
import sys
import time
from http import HTTPStatus

from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from telebot import TeleBot
from telebot.apihelper import ApiException
import requests
from requests.exceptions import RequestException

from exceptions import APIResponseError, TokenError

logger = logging.getLogger(__name__)
load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
LAST_MONTH = 30 * 24 * 60 * 60

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> bool:
    """Проверка наличия всех токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, value in tokens.items() if not value]

    if missing_tokens:
        error_message = (
            f'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )
        logger.critical(error_message)
        raise TokenError(error_message)

    return True


def get_api_answer(timestamp):
    """Получает ответ от API сервиса Яндекс Практикум.Домашка."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        logger.info('Сервис Яндекс Практикум.Домашка работает.')
    except requests.exceptions.RequestException as error:
        raise APIResponseError(f'Ошибка запроса: {error}')

    if response.status_code != HTTPStatus.OK:
        raise APIResponseError(
            f'Эндпоинт недоступен. Код ответа: {response.status_code}'
        )
    logger.info('Запрос выполнен успешно')

    return response.json()


def check_response(response):
    """Функция проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        raise TypeError('В ответе API отсутствует ключ "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Домашние работы должны быть в формате списка')


def parse_status(homework):
    """Извлекает статус домашней работы и формирует сообщение."""
    for key in ('status', 'homework_name'):
        if key not in homework:
            raise APIResponseError(
                f'Отсутствует ключ "{key}" в домашней работе'
            )
    status, homework_name = homework['status'], homework['homework_name']
    if status not in HOMEWORK_VERDICTS:
        raise APIResponseError(f'Неожиданный статус домашней работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в указанный Telegram чат."""
    try:
        logger.info(f"Отправка сообщения {message}")
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение: "{message}"')
        return True
    except (ApiException, RequestException) as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')
        return False


def setup_logging():
    """Настройка логирования."""
    os.makedirs('logs', exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Обработчик для вывода в stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(formatter)

    # Обработчик для записи в файл с ротацией
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=1024 * 1024,
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)
    logger.addHandler(file_handler)

    return logger


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except TokenError:
        sys.exit(1)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - LAST_MONTH
    """while not send_message(bot, 'Бот запущен и начал мониторинг'):
        time.sleep(60)"""
    message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response['homeworks']
            message = parse_status(homeworks[0]) if homeworks else None

            if not message:
                logger.debug('Новых статусов нет')
            elif send_message(bot, message):
                timestamp = response.get('current_date', timestamp)

        except Exception as error:
            error_message = str(error)
            logger.error(f'Сбой в работе программы: {error_message}')
            if message != error_message and send_message(bot, error_message):
                message = error_message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger = setup_logging()
    main()
