import boto3

dynamo_db = boto3.resource('dynamodb')


# Обработчик входящих сообщений
def handle(event, context):
    table = dynamo_db.Table("tasks")
    table.put_item(Item={'chat_id': event['chat_id'], 'tasks': event['tasks']})
