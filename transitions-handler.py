import boto3

dynamo_db = boto3.resource('dynamodb')


# Обработчик входящих сообщений
def handle(event, context):
    chat_id = str(event['chat_id'])
    table = dynamo_db.Table("chat_data")
    response = table.get_item(Key={'chat_id': chat_id})

    if 'Item' in response:
        return response['Item']['data']
    else:
        return None
