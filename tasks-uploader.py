import json
import logging
from json import JSONDecodeError

import requests
from requests import ReadTimeout

CHAT_ID = ''
BOARD_ID = ''
JIRA_USER_NAME = ''
JIRA_USER_PASSWORD = ''
GET_SPRINT_ID_URL = 'http://jira/rest/agile/1.0/board/{board_id}/sprint?state=active'.format(board_id=BOARD_ID)
SPRINT_TASK_STATUSES = '\'BACKLOG\', \'IN PROGRESS\', \'CODE REVIEW\''
GET_SPRINT_TASKS_URL = 'http://jira/rest/agile/1.0/board/{board_id}/sprint/{sprint_id}/issue?jql=status in ({' \
                       'task_statuses})' \
                       '&fields=summary,assignee,status,parent'
TASKS_UPLOAD_URL = 'https://wb9fbkheca.execute-api.us-east-2.amazonaws.com/v0/upload'
DEFAULT_TIMEOUT_IN_SECONDS = 10
TASK_SORTING_ORDER = ['BACKLOG', 'IN PROGRESS', 'CODE REVIEW']

logging.basicConfig(level=logging.INFO)


def get_active_sprint_id():
    try:
        logging.info('Getting sprint_id...')
        response = requests.get(url=GET_SPRINT_ID_URL, auth=(JIRA_USER_NAME, JIRA_USER_PASSWORD), timeout=DEFAULT_TIMEOUT_IN_SECONDS)
        check_response_status(response)

        json_response = parse_json(response.text)
        if not json_response:
            raise TaskUploaderException('Active sprint not found.')

        if 'values' not in json_response:
            raise TaskUploaderException('Active sprint not found.')

        values = json_response['values']
        if not values:
            raise TaskUploaderException('Active sprint not found.')

        if 'id' not in values[0]:
            raise TaskUploaderException('Active sprint not found.')

        sprint_id = values[0]['id']
        if not sprint_id:
            raise TaskUploaderException('Active sprint not found.')

        logging.info('Done.')

        return sprint_id
    except ReadTimeout:
        logging.error('Error timeout')
        raise TaskUploaderException('Active sprint not found.')


def get_tasks(sprint_id):
    logging.info('Getting tasks...')
    url = GET_SPRINT_TASKS_URL.format(board_id=BOARD_ID, sprint_id=sprint_id, task_statuses=SPRINT_TASK_STATUSES)
    response = requests.get(url=url, auth=(JIRA_USER_NAME, JIRA_USER_PASSWORD))
    json_response = parse_json(response.text)

    if 'issues' not in json_response:
        raise TaskUploaderException('Failed to get task list.')

    task_list = []
    for task in json_response['issues']:
        task_item = dict()
        if 'key' in task:
            task_item['key'] = task['key']
        if 'fields' in task:
            fields = task['fields']
            if 'summary' in fields:
                task_item['summary'] = fields['summary']
            if 'assignee' in fields:
                if fields['assignee'] is not None:
                    task_item['assignee_display_name'] = fields['assignee'].get('displayName', None)
            if 'status' in fields:
                if fields['status'] is not None:
                    task_item['status_name'] = fields['status'].get('name', None)
            if 'parent' in fields:
                if fields['parent'] is not None:
                    parent = fields['parent']
                    task_item['parent_key'] = parent.get('key', None)
                    if parent['fields'] is not None:
                        task_item['parent_summary'] = parent['fields'].get('summary', None)
        task_list.append(task_item)

    check_response_status(response)
    return task_list


def to_group_tasks(tasks):
    dictionary = dict()
    for task in tasks:
        if 'parent_key' in task:
            if task['parent_key'] not in dictionary:
                dictionary[task['parent_key']] = task
            if 'sub_tasks' not in dictionary[task['parent_key']]:
                dictionary[task['parent_key']].setdefault('sub_tasks', [])
            dictionary[task['parent_key']]['sub_tasks'].append(task)
        else:
            dictionary[task['key']] = task

    return list(dictionary.values())


def sort_list_of_items(list_of_items):
    list_of_items.sort(key=lambda item: TASK_SORTING_ORDER.index(item['status_name'].upper()))


def to_sort_tasks(tasks):
    sort_list_of_items(tasks)
    for task in tasks:
        if 'sub_tasks' in task:
            sort_list_of_items(task['sub_tasks'])
    return tasks


def parse_json(text):
    try:
        return json.loads(text)
    except JSONDecodeError:
        logging.error('Error parsing json document')
        return None


def check_response_status(response):
    if response.status_code != requests.codes.ok:
        raise TaskUploaderException('Error response status: {}'.format(response.status_code))


def task_list_to_json(tasks, chat_id):
    dictionary = dict()
    dictionary['chat_id'] = chat_id
    dictionary['tasks'] = tasks
    return json.dumps(dictionary)


def upload_tasks(tasks_json):
    logging.info('Uploading tasks...')
    response = requests.post(url=TASKS_UPLOAD_URL, data=tasks_json)
    check_response_status(response)


class TaskUploaderException(BaseException):
    pass


if __name__ == "__main__":

    try:
        upload_tasks(task_list_to_json(to_sort_tasks(to_group_tasks(get_tasks(get_active_sprint_id()))), CHAT_ID))
    except TaskUploaderException as ex:
        logging.error(ex)
    except BaseException as ex:
        logging.exception(ex)