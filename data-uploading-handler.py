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

    data['tasks'] = event['data']['tasks']
    data['push_analytics'] = event['data']['push_analytics']

    if 'transitions' in data:
        del data['transitions']

    if 'backlog' in data:
        del data['backlog']

    table.put_item(Item={'chat_id': chat_id, 'data': data})
