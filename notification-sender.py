import datetime

import boto3
import telebot
from boto3.dynamodb.conditions import Key

TOKEN = ''
PRE_NOTIFICATION_OFFSET_MINUTES = 1
NO_TASKS = 'Задачи отсутствуют.'


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


def show_tasks(chat_id):
    table = dynamo_db.Table("tasks")
    response = table.get_item(Key={'chat_id': chat_id})

    if 'Item' in response:
        tasks = response['Item']['tasks']
        sb = []
        current_status = None
        for task in tasks:
            if task['status_name'] != current_status:
                sb.append('\n')
                sb.append('Статус: ')
                sb.append(task['status_name'])
                sb.append('\n')
            sb.append(' ')
            sb.append(task['key'])
            sb.append(' ')
            sb.append('*')
            sb.append(task['summary'])
            sb.append('*')
            sb.append('\n')
            sb.append('  - назначена на: ')
            if 'assignee_display_name' in task:
                sb.append(task['assignee_display_name'])
            else:
                sb.append('-')
            sb.append('\n')
            current_status = task['status_name']

        bot.send_message(parse_mode='markdown', chat_id=chat_id, text=''.join(sb))
    else:
        bot.send_message(chat_id, NO_TASKS)