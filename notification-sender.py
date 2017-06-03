import telebot
import boto3
import datetime

from boto3.dynamodb.conditions import Key

TOKEN = ''

bot = telebot.TeleBot(TOKEN)
dynamodb = boto3.resource('dynamodb')

def handle(event, context):
    
    hour = str(datetime.datetime.utcnow().hour)
    if len(hour) == 1:
        hour = '0' + hour
    
    minute = str(datetime.datetime.utcnow().minute)
    if len(minute) == 1:
        minute = '0' + minute
    
    table = dynamodb.Table("notification")
    response = table.query(
        IndexName='notification_time-index',
        KeyConditionExpression=Key('notification_time').eq(hour + minute)
    )
    
    if response:
        for item in response['Items']:
            bot.send_message(item['chat_id'], item['message'])        
    
