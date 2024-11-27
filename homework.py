import logging
import os
import requests
import sys
import time
from http import HTTPStatus

from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import APIResponseError, TokenError

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
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


def check_tokens():
    """Проверка наличия всех токенов."""
    env_tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    if not all(env_tokens):
        raise TokenError
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
        if response.status_code != HTTPStatus.OK:
            raise APIResponseError(
                f'Эндпоинт недоступен. Код ответа: {response.status_code}'
            )
        logger.info('Запрос выполнен успешно')
        return response.json()
    except requests.exceptions.RequestException as error:
        logger.error(f'Ошибка при запросе к API: {error}')
        raise APIResponseError(f'Ошибка запроса: {error}')


def check_response(response):
    """Функция проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        raise TypeError('В ответе API отсутствует ключ "homeworks"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Домашние работы должны быть в формате списка')
    return homeworks


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
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except TokenError:
        logger.critical('Отсутствуют обязательные переменные окружения!')
        sys.exit(1)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - LAST_MONTH
    send_message(bot, 'Бот запущен и начал мониторинг')
    last_error_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
            else:
                logger.debug('Новых статусов нет')
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            error_message = str(error)
            logger.error(f'Сбой в работе программы: {error_message}')
            if error_message != last_error_message:
                send_message(bot, error_message)
                last_error_message = error_message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
