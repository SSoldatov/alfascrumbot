import json
import logging
from itertools import repeat
from json import JSONDecodeError

import requests
from requests import ReadTimeout

CHAT_ID = ''
BOARD_ID = ''
JIRA_USER_NAME = ''
JIRA_USER_PASSWORD = ''
JIRA_HOST = 'http://jira'
GET_SPRINT_ID_URL = '{jira_host}/rest/agile/1.0/board/{board_id}/sprint?state=active'.format(jira_host=JIRA_HOST, board_id=BOARD_ID)
TASK_SORTING_ORDER = ['BACKLOG', 'TODO', 'IN PROGRESS', 'CODE REVIEW']
SPRINT_TASK_STATUSES = ', '.join("'{0}'".format(x) for x in TASK_SORTING_ORDER)
GET_SPRINT_TASKS_URL = '{jira_host}/rest/agile/1.0/board/{board_id}/sprint/{sprint_id}/issue?jql=status in ({' \
                       'task_statuses})' \
                       '&fields=summary,assignee,status,parent'

TASK_TRANSITIONS_URL = '{jira_host}/rest/api/latest/issue/{task_id}/transitions'

TASKS_UPLOAD_URL = 'https://wb9fbkheca.execute-api.us-east-2.amazonaws.com/v0/upload'
GET_TASK_TRANSITIONS_URL = 'https://wb9fbkheca.execute-api.us-east-2.amazonaws.com/v0/transitions'
DEFAULT_TIMEOUT_IN_SECONDS = 10

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
    url = GET_SPRINT_TASKS_URL.format(jira_host=JIRA_HOST, board_id=BOARD_ID, sprint_id=sprint_id, task_statuses=SPRINT_TASK_STATUSES)
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
    if response.status_code >= 400:
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


def put_task_to_next_transition(task_id, repeat_count=1):
    for _ in repeat(None, int(repeat_count)):
        logging.info('Putting task %s to next transition...', task_id)
        transition_id = get_next_transitions_id(task_id)
        url = TASK_TRANSITIONS_URL.format(jira_host=JIRA_HOST, task_id=task_id)
        headers = {'Content-type': 'application/json'}
        data = {'transition': {'id': transition_id}}
        response = requests.post(url=url, auth=(JIRA_USER_NAME, JIRA_USER_PASSWORD), data=json.dumps(data), headers=headers)
        check_response_status(response)
        logging.info('Done.')


def get_next_transitions_id(task_id):
    try:
        logging.info('Getting next transition for task %s...', task_id)
        url = TASK_TRANSITIONS_URL.format(jira_host=JIRA_HOST, task_id=task_id)
        response = requests.get(url=url, auth=(JIRA_USER_NAME, JIRA_USER_PASSWORD), timeout=DEFAULT_TIMEOUT_IN_SECONDS)
        check_response_status(response)

        json_response = parse_json(response.text)
        if not json_response:
            raise TaskUploaderException('Next transition not found.')
        if 'transitions' not in json_response:
            raise TaskUploaderException('Next transition not found.')
        transitions = json_response['transitions']
        if not transitions:
            raise TaskUploaderException('Next transition not found.')
        if 'id' not in transitions[0]:
            raise TaskUploaderException('Next transition not found.')
        transition_id = transitions[0]['id']

        logging.info('Done.')
        return transition_id
    except ReadTimeout:
        logging.error('Error timeout')
        raise TaskUploaderException('Next transition not found.')


def get_next_status(current_status):
    current_index = TASK_SORTING_ORDER.index(current_status)
    next_index = current_index + 1
    if next_index > len(TASK_SORTING_ORDER) - 1:
        return None
    return TASK_SORTING_ORDER[next_index]


def get_transitions(chat_id):
    logging.info('Getting transitions...')
    params = {'chat_id': chat_id}
    response = requests.get(url=GET_TASK_TRANSITIONS_URL, params=params)
    check_response_status(response)
    json_response = parse_json(response.text)
    return json_response


def handle_transitions(chat_id):
    transitions = get_transitions(chat_id)
    if transitions:
        for task_id in transitions:
            count = transitions[task_id]
            put_task_to_next_transition(task_id, count)


class TaskUploaderException(BaseException):
    pass


if __name__ == "__main__":
    try:
        handle_transitions(CHAT_ID)
        upload_tasks(task_list_to_json(to_sort_tasks(to_group_tasks(get_tasks(get_active_sprint_id()))), CHAT_ID))
    except TaskUploaderException as ex:
        logging.error(ex)
    except BaseException as ex:
        logging.exception(ex)
