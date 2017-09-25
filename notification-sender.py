import datetime

from boto3.dynamodb.conditions import Key

from commons import add_leading_zero
from commons import bot
from commons import dynamo_db
from commons import show_tasks

PRE_NOTIFICATION_OFFSET_MINUTES = 1


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
