import telebot
import time
import re
import boto3
import datetime
from boto3.dynamodb.conditions import Key

TOKEN = ''
DEFAULT_MESSAGE = 'Сообщение по умолчанию'
DEFAULT_TIME_ZONE_OFFSET = '+3'

bot = telebot.TeleBot(TOKEN)
dynamodb = boto3.resource('dynamodb')

# Обработчик входящих сообщений
def handle(event, context):
    update = telebot.types.Update.de_json(str(event).replace("'", "\"").replace("True", "true"))
    bot.process_new_messages([update.message])
    time.sleep(1.5)

# Обработчик команд '/start' и '/help'.
@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    r = []
    r.append('/add <ЧЧ:MM> <ТЕКСТ ОПОВЕЩЕНИЯ> - добавить новое оповещение в указанное время, для текущего чата.')
    r.append('\n')
    r.append(' -время указывается по UTC.')
    r.append('\n')
    r.append(' -если текст оповещения отсутствует, будет использоваться сообщение по умолчанию.')
    r.append('\n')
    r.append(' -если существует ранее добавленное оповещение в указанное время, оно будет обновлено.')
    r.append('\n')
    r.append('\n')
    r.append('/list - вывести список оповещений для текущего чата.')
    r.append('\n')
    r.append('\n')
    r.append('/remove <ЧЧ:MM> - удалить оповещение в указанное время, для текущего чата.')
    r.append('\n')
    r.append('\n')
    r.append('/removeall - удалить все оповещения для текущего чата.')

    bot.send_message(message.chat.id, ''.join(r))

# Обработчик команд '/add'.
@bot.message_handler(commands=['add'])
def handle_add(message):
    try:
        pattern_string = "^/.*? ([01][0-9]|2[0-3]):([0-5][0-9])([+-][0-9][0-9]?)?( (.*))?$"
        pattern = re.compile(pattern_string)
        match_result = pattern.match(message.text)
        if match_result:
            hours = match_result.group(1)
            minutes = match_result.group(2)
            time_zone = match_result.group(3)
            messageText = match_result.group(5)
            chat_id = str(message.chat.id)
            notification_time = hours + minutes
            id = chat_id+notification_time

            if not messageText:
                messageText = DEFAULT_MESSAGE
                
            table = dynamodb.Table("notification")
            
            table.put_item(
                Item={
                    'id': id,
                    'notification_time': hours + minutes,
                    'chat_id': chat_id,
                    'message': messageText
                })
            bot.send_message(message.chat.id, 'Ok')
        else:
            bot.send_message(message.chat.id, 'Не верный формат команды')
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, 'Ошибка')

	
# Обработчик команд '/remove'.
@bot.message_handler(commands=['remove'])
def handle_remove(message):
    try:
        pattern_string = "^/.*? ([01][0-9]|2[0-3]):([0-5][0-9])$"   
        pattern = re.compile(pattern_string)
        match_result = pattern.match(message.text)
        if match_result:
            hours = match_result.group(1)
            minutes = match_result.group(2)
            chat_id = str(message.chat.id)
            notification_time = hours + minutes
            id = chat_id+notification_time
            table = dynamodb.Table("notification")
            table.delete_item(
                Key={
                    'id': id
                })
            bot.send_message(message.chat.id, 'Ok')
        else:
            bot.send_message(message.chat.id, 'Не верный формат команды')
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, 'Ошибка')    

# Обработчик команд '/removeall'.
@bot.message_handler(commands=['removeall'])
def handle_remove_all(message):
    try:
        table = dynamodb.Table("notification")
        response = table.query(
            IndexName='chat_id-index',
            KeyConditionExpression=Key('chat_id').eq(str(message.chat.id))
        )
        for item in response['Items']:
            table.delete_item(
                Key={
                    'id': item['id']
                })
        
        bot.send_message(message.chat.id, 'Ok')
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, 'Ошибка')    

# Обработчик команд '/list'.
@bot.message_handler(commands=['list'])
def handle_list(message):
    
    try:
        table = dynamodb.Table("notification")
        response = table.query(
            IndexName='chat_id-index',
            KeyConditionExpression=Key('chat_id').eq(str(message.chat.id))
        )
        
        r = []
        for item in response['Items']:
            r.append(item['notification_time'][:2])
            r.append(':')
            r.append(item['notification_time'][2:])
            r.append(' - ')
            r.append(item['message'])
            r.append('\n')
            
        if r:
            bot.send_message(message.chat.id, ''.join(r))
        else:
            bot.send_message(message.chat.id, 'Оповещения отсутствуют')
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, 'Ошибка')