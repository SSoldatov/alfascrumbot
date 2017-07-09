import datetime

import boto3
import telebot
from boto3.dynamodb.conditions import Key

TOKEN = ''
PRE_NOTIFICATION_OFFSET_MINUTES = 1
NO_TASKS = 'Задачи отсутствуют.'

EMOJI_BACKLOG = u'\u23FA\uFE0F'
EMOJI_TODO = u'\u23F8\uFE0F'
EMOJI_IN_PROGRESS = u'\u25B6\uFE0F'
EMOJI_CODE_REVIEW = u'\u23EF\uFE0F'
EMOJI_DONE = u'\u2714\uFE0F'

DEFAULT_INDENT = '    '

bot = telebot.TeleBot(TOKEN)
dynamo_db = boto3.resource('dynamodb')


def handle(event, context):
    now_time = datetime.datetime.utcnow()
    notification_time = add_leading_zero(now_time.hour) + add_leading_zero(now_time.minute)

    pre_time = now_time + datetime.timedelta(minutes=PRE_NOTIFICATION_OFFSET_MINUTES)
    pre_notification_time = add_leading_zero(pre_time.hour) + add_leading_zero(pre_time.minute)

    send_notification(notification_time, 'message', True)
    send_notification(pre_notification_time, 'pre_message', False)


def send_notification(notification_time, message_attribute_name, is_show_tasks):
    table = dynamo_db.Table("notification")
    response = table.query(IndexName='notification_time-index', KeyConditionExpression=Key('notification_time').eq(notification_time))

    if response:
        for item in response['Items']:
            bot.send_message(item['chat_id'], item[message_attribute_name])
            if is_show_tasks:
                show_tasks(item['chat_id'])


def add_leading_zero(hour, width=2):
    return str(hour).zfill(width)


def get_emoji_alias_name(status_name):
    status_name = status_name.upper()
    if status_name == 'BACKLOG':
        return EMOJI_BACKLOG
    if status_name == 'TODO':
        return EMOJI_TODO
    elif status_name == 'IN PROGRESS':
        return EMOJI_IN_PROGRESS
    elif status_name == 'CODE REVIEW':
        return EMOJI_CODE_REVIEW
    elif status_name == 'DONE':
        return EMOJI_DONE
    else:
        return ''


def show_tasks(chat_id):
    data = get_chat_data(chat_id)
    if 'tasks' in data:
        tasks = data['tasks']
        if tasks:
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
                sb.append('/tonextstatus\_')
                sb.append(task['key'].replace("-", "\_"))
                sb.append('\n')
                sb.append('\n')
                if 'sub_tasks' in task:
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
                        sb.append(DEFAULT_INDENT)
                        sb.append('/tonextstatus\_')
                        sb.append(sub_task['key'].replace("-", "\_"))
                        sb.append('\n')
                        sb.append('\n')
                    sb.append('\n')

            bot.send_message(parse_mode='markdown', chat_id=chat_id, text=''.join(sb))
        else:
            bot.send_message(chat_id, NO_TASKS)
    else:
        bot.send_message(chat_id, NO_TASKS)


def get_data(response):
    if 'Item' in response:
        data = response['Item']['data']
    else:
        data = dict()
    return data


def get_chat_data(chat_id):
    table = dynamo_db.Table("chat_data")
    return get_data(table.get_item(Key={'chat_id': chat_id}))
