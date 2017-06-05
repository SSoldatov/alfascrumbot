import re
import time

import boto3
import telebot
from boto3.dynamodb.conditions import Key

TOKEN = ''
DEFAULT_MESSAGE = 'Daily standup meeting'
MOSCOW_TIME_ZONE_OFFSET = +3

BOT_START_WORK_HOUR = 9
BOT_END_WORK_HOUR = 19

OK_MESSAGE = 'Ok'
ERROR_MESSAGE = 'Ошибка'
WRONG_INPUT_DATA_MESSAGE = 'Неверный формат команды'

BOT_OPENING_HOURS_MESSAGE = 'Часы работы бота ' + str(BOT_START_WORK_HOUR) + ':00 по ' + str(BOT_END_WORK_HOUR) + ':00, время московское.'

bot = telebot.TeleBot(TOKEN)

dynamo_db = boto3.resource('dynamodb')


# Обработчик входящих сообщений
def handle(event, context):
    update = telebot.types.Update.de_json(str(event).replace("'", "\"").replace("True", "true"))
    bot.process_new_messages([update.message])
    time.sleep(1.5)


# Обработчик команд '/start' и '/help'.
@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    text_message = '/add <ЧЧ:MM> <ТЕКСТ ОПОВЕЩЕНИЯ> - добавить новое оповещение в указанное время, для текущего чата.' \
                   '\n' \
                   ' -время указывается московское (c 9:00 до 19:00).' \
                   '\n' \
                   ' -если текст оповещения отсутствует, будет использоваться сообщение по умолчанию.' \
                   '\n' \
                   ' -если существует ранее добавленное оповещение в указанное время, оно будет обновлено.' \
                   '\n' \
                   '\n' \
                   '/list - вывести список оповещений для текущего чата.' \
                   '\n' \
                   '\n' \
                   '/remove <ЧЧ:MM> - удалить оповещение в указанное время, для текущего чата.' \
                   '\n' \
                   '\n' \
                   '/removeall - удалить все оповещения для текущего чата.'

    bot.send_message(message.chat.id, text_message)


# Обработчик команд '/add'.
@bot.message_handler(commands=['add'])
def handle_add(message):
    try:
        pattern_string = "^/.*? ([01]?[0-9]|2[0-3]):([0-5][0-9])([+-][0-9][0-9]?)?( (.*))?$"
        pattern = re.compile(pattern_string)
        match_result = pattern.match(message.text)
        if match_result:
            hour = match_result.group(1)

            if not check_input_hour(hour):
                bot.send_message(message.chat.id, BOT_OPENING_HOURS_MESSAGE)
                return

            hour = normalize_hour(hour)

            minute = match_result.group(2)
            message_text = match_result.group(5)
            chat_id = str(message.chat.id)
            notification_time = hour + minute
            notification_id = chat_id + notification_time

            if not message_text:
                message_text = DEFAULT_MESSAGE

            table = dynamo_db.Table("notification")

            table.put_item(Item={'id': notification_id, 'notification_time': hour + minute, 'chat_id': chat_id, 'message': message_text})
            bot.send_message(message.chat.id, OK_MESSAGE)
        else:
            bot.send_message(message.chat.id, WRONG_INPUT_DATA_MESSAGE)
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, ERROR_MESSAGE)


# Обработчик команд '/remove'.
@bot.message_handler(commands=['remove'])
def handle_remove(message):
    try:
        pattern_string = "^/.*? ([01]?[0-9]|2[0-3]):([0-5][0-9])$"
        pattern = re.compile(pattern_string)
        match_result = pattern.match(message.text)
        if match_result:
            hour = normalize_hour(match_result.group(1))
            minutes = match_result.group(2)
            chat_id = str(message.chat.id)
            notification_time = hour + minutes
            notification_id = chat_id + notification_time
            table = dynamo_db.Table("notification")
            table.delete_item(Key={'id': notification_id})
            bot.send_message(message.chat.id, OK_MESSAGE)
        else:
            bot.send_message(message.chat.id, WRONG_INPUT_DATA_MESSAGE)
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, ERROR_MESSAGE)


# Обработчик команд '/removeall'.
@bot.message_handler(commands=['removeall'])
def handle_remove_all(message):
    try:
        table = dynamo_db.Table("notification")
        response = table.query(IndexName='chat_id-index', KeyConditionExpression=Key('chat_id').eq(str(message.chat.id)))
        for item in response['Items']:
            table.delete_item(Key={'id': item['id']})

        bot.send_message(message.chat.id, OK_MESSAGE)
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, ERROR_MESSAGE)


# Обработчик команд '/list'.
@bot.message_handler(commands=['list'])
def handle_list(message):
    try:
        table = dynamo_db.Table("notification")
        response = table.query(IndexName='chat_id-index', KeyConditionExpression=Key('chat_id').eq(str(message.chat.id)))

        sb = []
        for item in response['Items']:
            sb.append(hour_to_moscow(item['notification_time'][:2]))
            sb.append(':')
            sb.append(item['notification_time'][2:])
            sb.append(' - ')
            sb.append(item['message'])
            sb.append('\n')

        if sb:
            bot.send_message(message.chat.id, ''.join(sb))
        else:
            bot.send_message(message.chat.id, 'Оповещения отсутствуют')
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, ERROR_MESSAGE)


def check_input_hour(hour):
    return BOT_START_WORK_HOUR <= int(hour) <= BOT_END_WORK_HOUR


def hour_to_utc(hour):
    return str(int(hour) - MOSCOW_TIME_ZONE_OFFSET)


def hour_to_moscow(hour):
    return str(int(hour) + MOSCOW_TIME_ZONE_OFFSET)


def normalize_hour(hour):
    hour = hour_to_utc(hour)

    if len(hour) == 1:
        hour = '0' + hour

    return hour


if __name__ == "__main__":
    print(check_input_hour(1))
