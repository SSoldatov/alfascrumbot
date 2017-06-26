import datetime
import re
import time
import traceback

import boto3
import telebot
from boto3.dynamodb.conditions import Key

TOKEN = ''

PRE_NOTIFICATION_OFFSET_IN_MINUTES = 1

DEFAULT_MESSAGE = 'Daily standup meeting.'
DEFAULT_PRE_MESSAGE = 'Daily standup meeting will begin in {} minute.'.format(PRE_NOTIFICATION_OFFSET_IN_MINUTES)

MOSCOW_TIME_ZONE_OFFSET_HOURS = '+03'
DEFAULT_TIME_ZONE_OFFSET = MOSCOW_TIME_ZONE_OFFSET_HOURS

NO_NOTIFICATIONS_MESSAGE = 'Оповещения отсутствуют.'
NO_TIME_ZONE_OFFSET_MESSAGE = 'Часовой пояс не установлен, используется московское время.'
OK_MESSAGE = 'Ok'
ERROR_MESSAGE = 'Ошибка'
WRONG_INPUT_DATA_MESSAGE = 'Неверный формат команды.'
NO_TASKS = 'Задачи отсутствуют.'

EMOJI_BACKLOG = u'\u23F8\uFE0F'
EMOJI_IN_PROGRESS = u'\u25B6\uFE0F'
EMOJI_CODE_REVIEW = u'\u23EF\uFE0F'
EMOJI_DONE = u'\u2714\uFE0F'

DEFAULT_INDENT = '    '

bot = telebot.TeleBot(TOKEN)

dynamo_db = boto3.resource('dynamodb')


# Обработчик входящих сообщений
def handle(event, context):
    update = telebot.types.Update.de_json(str(event).replace("'", "\"").replace("True", "true"))
    bot.process_new_messages([update.message])
    time.sleep(1.5)


# Обработчик команд '/settmz'.
@bot.message_handler(commands=['settmz'])
def handle_set_timezone_offset(message):
    try:
        pattern_string = "^/.*? ([+-])([01]?[0-9]|2[0-3])$"
        pattern = re.compile(pattern_string)
        match_result = pattern.match(message.text)
        if match_result:
            time_zone_offset = match_result.group(1) + add_leading_zero(match_result.group(2))
            table = dynamo_db.Table("timezone")
            table.put_item(Item={'chat_id': str(message.chat.id), 'time_zone_offset': time_zone_offset})
            bot.send_message(message.chat.id, OK_MESSAGE)
        else:
            bot.send_message(message.chat.id, WRONG_INPUT_DATA_MESSAGE)
    except Exception:
        print(traceback.format_exc())
        bot.send_message(message.chat.id, ERROR_MESSAGE)


# Обработчик команд '/showtmz'.
@bot.message_handler(commands=['showtmz'])
def handle_show_timezone_offset(message):
    try:
        offset = read_offset(message.chat.id)
        if offset:
            bot.send_message(message.chat.id, offset)
        else:
            bot.send_message(message.chat.id, NO_TIME_ZONE_OFFSET_MESSAGE)
    except Exception:
        print(traceback.format_exc())
        bot.send_message(message.chat.id, ERROR_MESSAGE)


# Обработчик команд '/start' и '/help'.
@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    text_message = '/settmz <+/-ЧЧ> - указать часовой пояс для текущего чата (смещение от UTC в часах).' \
                   '\n' \
                   '\n' \
                   '/showtmz - показать часовой пояс для текущего чата (смещение от UTC в часах).' \
                   '\n' \
                   '\n' \
                   '/add <ЧЧ:MM> <ТЕКСТ ОПОВЕЩЕНИЯ> <ТЕКСТ ПРЕДВАРИТЕЛЬНОГО ОПОВЕЩЕНИЯ> - добавить новое оповещение в указанное время,' \
                   ' для текущего чата.' \
                   '\n' \
                   '{indent}-при указании времени используется часовой пояс заданный командой /settmz.' \
                   '\n' \
                   '{indent}-если часовой пояс не указан, используется время московское.' \
                   '\n' \
                   '{indent}-если текст оповещения отсутствует, будет использоваться сообщение по умолчанию.' \
                   '\n' \
                   '{indent}-если текст предварительного оповещения отсутствует, будет использоваться сообщение по умолчанию.' \
                   '\n' \
                   '{indent}-предварительное оповещение будет отправлено за {pre_notification_offset_in_minutes}' \
                   ' минуту до указанного времени.' \
                   '\n' \
                   '{indent}-если существует ранее добавленное оповещение в указанное время, оно будет обновлено.' \
                   '\n' \
                   '\n' \
                   '/list - вывести список оповещений для текущего чата.' \
                   '\n' \
                   '\n' \
                   '/remove <ЧЧ:MM> - удалить оповещение в указанное время, для текущего чата.' \
                   '\n' \
                   '\n' \
                   '/removeall - удалить все оповещения для текущего чата.' \
                   '\n' \
                   '\n' \
                   '/tasks - вывести список загруженных для текущего чата задач.' \
                   '\n' \
                   '    -под номером задачи выводится emoji символ, обозначающий ее статус:' \
                   '\n' \
                   '{indent}{indent}{backlog_emoji} - BACKLOG' \
                   '\n' \
                   '{indent}{indent}{in_progress_emoji} - In Progress' \
                   '\n' \
                   '{indent}{indent}{code_review_emoji} - Code review' \
                   '\n' \
                   '\n' \
                   '/removetasks - удалить все загруженные для текущего чата задачи.' \
        .format(pre_notification_offset_in_minutes=PRE_NOTIFICATION_OFFSET_IN_MINUTES,
                indent=DEFAULT_INDENT, backlog_emoji=EMOJI_BACKLOG, in_progress_emoji = EMOJI_IN_PROGRESS,
                code_review_emoji=EMOJI_CODE_REVIEW)

    bot.send_message(message.chat.id, text_message)


# Обработчик команд '/add'.
@bot.message_handler(commands=['add'])
def handle_add(message):
    try:
        pattern_string = "^/.*? ([01]?[0-9]|2[0-3]):([0-5][0-9])( ([^ ]*))?( ([^ ]*))?$"
        pattern = re.compile(pattern_string)
        match_result = pattern.match(message.text)
        if match_result:

            time_zone_offset = read_offset(message.chat.id)
            if not time_zone_offset:
                time_zone_offset = DEFAULT_TIME_ZONE_OFFSET

            hours = add_leading_zero(hour_to_utc(match_result.group(1), time_zone_offset))
            minutes = add_leading_zero(match_result.group(2))

            message_text = match_result.group(4)
            if not message_text:
                message_text = DEFAULT_MESSAGE

            pre_message_text = match_result.group(6)
            if not pre_message_text:
                pre_message_text = DEFAULT_PRE_MESSAGE

            chat_id = str(message.chat.id)
            notification_time = hours + minutes
            notification_id = chat_id + notification_time

            table = dynamo_db.Table("notification")
            table.put_item(Item={'id': notification_id, 'notification_time': hours + minutes, 'chat_id': chat_id, 'message': message_text,
                                 'pre_message': pre_message_text})

            bot.send_message(message.chat.id, OK_MESSAGE)
        else:
            bot.send_message(message.chat.id, WRONG_INPUT_DATA_MESSAGE)
    except Exception:
        print(traceback.format_exc())
        bot.send_message(message.chat.id, ERROR_MESSAGE)


# Обработчик команд '/remove'.
@bot.message_handler(commands=['remove'])
def handle_remove(message):
    try:
        pattern_string = "^/.*? ([01]?[0-9]|2[0-3]):([0-5][0-9])$"
        pattern = re.compile(pattern_string)
        match_result = pattern.match(message.text)
        if match_result:

            time_zone_offset = read_offset(message.chat.id)
            if not time_zone_offset:
                time_zone_offset = DEFAULT_TIME_ZONE_OFFSET

            hours = add_leading_zero(hour_to_utc(match_result.group(1), time_zone_offset))
            minutes = add_leading_zero(match_result.group(2))
            chat_id = str(message.chat.id)
            notification_time = hours + minutes
            notification_id = chat_id + notification_time

            table = dynamo_db.Table("notification")
            table.delete_item(Key={'id': notification_id})

            bot.send_message(message.chat.id, OK_MESSAGE)
        else:
            bot.send_message(message.chat.id, WRONG_INPUT_DATA_MESSAGE)
    except Exception:
        print(traceback.format_exc())
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
    except Exception:
        print(traceback.format_exc())
        bot.send_message(message.chat.id, ERROR_MESSAGE)


# Обработчик команд '/list'.
@bot.message_handler(commands=['list'])
def handle_list(message):
    try:

        time_zone_offset = read_offset(message.chat.id)
        if not time_zone_offset:
            time_zone_offset = DEFAULT_TIME_ZONE_OFFSET

        table = dynamo_db.Table("notification")
        response = table.query(IndexName='chat_id-index', KeyConditionExpression=Key('chat_id').eq(str(message.chat.id)))

        sb = []
        for item in response['Items']:
            sb.append(str(hour_to_timezone(item['notification_time'][:2], time_zone_offset)))
            sb.append(':')
            sb.append(item['notification_time'][2:])
            sb.append(' - ')
            sb.append(item['message'])
            sb.append(' - ')
            sb.append(item['pre_message'])
            sb.append('\n')

        if sb:
            bot.send_message(message.chat.id, ''.join(sb))
        else:
            bot.send_message(message.chat.id, NO_NOTIFICATIONS_MESSAGE)
    except Exception:
        print(traceback.format_exc())
        bot.send_message(message.chat.id, ERROR_MESSAGE)


# Обработчик команд '/tasks'.
@bot.message_handler(commands=['tasks'])
def handle_tasks(message):
    try:
        show_tasks(str(message.chat.id))
    except Exception:
        print(traceback.format_exc())
        bot.send_message(message.chat.id, ERROR_MESSAGE)


# Обработчик команд '/removetasks'.
@bot.message_handler(commands=['removetasks'])
def handle_tasks(message):
    try:
        table = dynamo_db.Table("tasks")
        chat_id = str(message.chat.id)
        table.delete_item(Key={'chat_id': chat_id})
        bot.send_message(chat_id, OK_MESSAGE)
    except Exception:
        print(traceback.format_exc())
        bot.send_message(message.chat.id, ERROR_MESSAGE)


def get_emoji_alias_name(status_name):
    if status_name == 'BACKLOG':
        return EMOJI_BACKLOG
    elif status_name == 'In Progress':
        return EMOJI_IN_PROGRESS
    elif status_name == 'Code review':
        return EMOJI_CODE_REVIEW
    elif status_name == 'Done':
        return EMOJI_DONE
    else:
        return ''


def show_tasks(chat_id):
    table = dynamo_db.Table("tasks")
    response = table.get_item(Key={'chat_id': chat_id})

    if 'Item' in response:
        tasks = response['Item']['tasks']
        sb = []
        for task in tasks:
            sb.append('*')
            sb.append(task['key'])
            sb.append(' ')
            sb.append(task['summary'])
            sb.append('*')
            sb.append('\n')
            sb.append(get_emoji_alias_name(task['status_name']))
            if 'assignee_display_name' in task:
                sb.append(' - ')
                sb.append(task['assignee_display_name'])
            sb.append('\n')
            sb.append('\n')
            for sub_task in task['sub_tasks']:
                sb.append(DEFAULT_INDENT)
                sb.append(sub_task['key'])
                sb.append(' ')
                sb.append('*')
                sb.append(sub_task['summary'])
                sb.append('*')
                sb.append('\n')
                sb.append(DEFAULT_INDENT)
                sb.append(get_emoji_alias_name(sub_task['status_name']))
                if 'assignee_display_name' in sub_task:
                    sb.append(' - ')
                    sb.append(sub_task['assignee_display_name'])
                sb.append('\n')
                sb.append('\n')
            sb.append('\n')

        bot.send_message(parse_mode='markdown', chat_id=chat_id, text=''.join(sb))
    else:
        bot.send_message(chat_id, NO_TASKS)


def hour_to_utc(hour, time_zone_offset):
    return (
    datetime.datetime.combine(datetime.date.today(), datetime.time(hour=int(hour))) - datetime.timedelta(hours=int(time_zone_offset))).hour


def hour_to_timezone(hour, time_zone_offset):
    return (
    datetime.datetime.combine(datetime.date.today(), datetime.time(hour=int(hour))) + datetime.timedelta(hours=int(time_zone_offset))).hour


def add_leading_zero(hour, width=2):
    return str(hour).zfill(width)


def read_offset(chat_id):
    table = dynamo_db.Table("timezone")
    response = table.get_item(Key={'chat_id': str(chat_id)})
    print(response)
    if 'Item' in response:
        return response['Item']['time_zone_offset']
    else:
        return None


if __name__ == "__main__":
    print('')
