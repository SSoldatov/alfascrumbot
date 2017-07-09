import boto3

dynamo_db = boto3.resource('dynamodb')


# Обработчик входящих сообщений
def handle(event, context):
    chat_id = str(event['chat_id'])
    table = dynamo_db.Table("chat_data")
    response = table.get_item(Key={'chat_id': chat_id})

    if 'Item' in response:
        data = response['Item']['data']
    else:
        data = dict()

    if 'transitions' in data:
        return data['transitions']
    else:
        return None
