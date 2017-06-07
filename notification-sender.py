import datetime

import boto3
import telebot
from boto3.dynamodb.conditions import Key

TOKEN = ''
PRE_NOTIFICATION_OFFSET_MINUTES = 1

bot = telebot.TeleBot(TOKEN)
dynamodb = boto3.resource('dynamodb')


def handle(event, context):
    now_time = datetime.datetime.utcnow()
    notification_time = add_leading_zero(now_time.hour) + add_leading_zero(now_time.minute)

    pre_time = now_time + datetime.timedelta(minutes=PRE_NOTIFICATION_OFFSET_MINUTES)
    pre_notification_time = add_leading_zero(pre_time.hour) + add_leading_zero(pre_time.minute)

    send_notification(notification_time, 'message')
    send_notification(pre_notification_time, 'pre_message')


def send_notification(notification_time, message_attribute_name):
    table = dynamodb.Table("notification")
    response = table.query(IndexName='notification_time-index', KeyConditionExpression=Key('notification_time').eq(notification_time))

    if response:
        for item in response['Items']:
            bot.send_message(item['chat_id'], item[message_attribute_name])


def add_leading_zero(hour, width=2):
    return str(hour).zfill(width)
