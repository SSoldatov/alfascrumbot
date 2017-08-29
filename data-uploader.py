import json
import logging
from itertools import repeat
from json import JSONDecodeError

import apiclient
import httplib2
import requests
from oauth2client.service_account import ServiceAccountCredentials
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
GOOGLE_DOCS_CREDENTIALS_FILE = 'google-docs-credentials.json'
TASK_TRANSITIONS_URL = '{jira_host}/rest/api/latest/issue/{task_id}/transitions'
TASKS_UPLOAD_URL = 'https://wb9fbkheca.execute-api.us-east-2.amazonaws.com/v0/upload'
GET_TASK_TRANSITIONS_URL = 'https://wb9fbkheca.execute-api.us-east-2.amazonaws.com/v0/transitions'
DEFAULT_TIMEOUT_IN_SECONDS = 10

logging.basicConfig(level=logging.INFO)

credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_DOCS_CREDENTIALS_FILE,
                                                               ['https://www.googleapis.com/auth/spreadsheets',
                                                                'https://www.googleapis.com/auth/drive'])
httpAuth = credentials.authorize(httplib2.Http())
service = apiclient.discovery.build('sheets', 'v4', http=httpAuth)


def get_active_sprint_id():
    try:
        logging.info('Getting sprint_id...')
        response = requests.get(url=GET_SPRINT_ID_URL, auth=(JIRA_USER_NAME, JIRA_USER_PASSWORD), timeout=DEFAULT_TIMEOUT_IN_SECONDS)
        check_response_status(response)

        json_response = parse_json(response.text)
        if not json_response:
            logging.info('Active sprint not found.')
            return None

        if 'values' not in json_response:
            logging.info('Active sprint not found.')
            return None

        values = json_response['values']
        if not values:
            logging.info('Active sprint not found.')
            return None

        if 'id' not in values[0]:
            logging.info('Active sprint not found.')
            return None

        sprint_id = values[0]['id']
        if not sprint_id:
            logging.info('Active sprint not found.')
            return None

        logging.info('Done.')

        return sprint_id
    except ReadTimeout:
        logging.error('Error timeout')
        logging.info('Active sprint not found.')
        return None


def get_tasks(sprint_id):
    logging.info('Getting tasks...')
    task_list = []
    if sprint_id is None:
        return task_list

    url = GET_SPRINT_TASKS_URL.format(jira_host=JIRA_HOST, board_id=BOARD_ID, sprint_id=sprint_id, task_statuses=SPRINT_TASK_STATUSES)
    response = requests.get(url=url, auth=(JIRA_USER_NAME, JIRA_USER_PASSWORD))
    json_response = parse_json(response.text)

    if 'issues' not in json_response:
        raise TaskUploaderException('Failed to get task list.')

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


def to_data_json(chat_id, tasks, push_analytics):
    dictionary = dict()
    dictionary['chat_id'] = chat_id
    data = dict()
    dictionary['data'] = data
    data['tasks'] = tasks
    data['push_analytics'] = push_analytics
    return json.dumps(dictionary)


def upload_data(data_json):
    logging.info('Uploading data...')
    response = requests.post(url=TASKS_UPLOAD_URL, data=data_json)
    check_response_status(response)


def put_task_to_next_transition(task_id, repeat_count=1):
    for _ in repeat(None, int(repeat_count)):
        logging.info('Putting task %s to next transition...', task_id)
        transition_id = get_next_transitions_id(task_id)
        if transition_id:
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
            logging.info("Next transition not found")
            return None
        if 'transitions' not in json_response:
            logging.info("Next transition not found")
            return None
        transitions = json_response['transitions']
        if not transitions:
            logging.info("Next transition not found")
            return None
        if 'id' not in transitions[0]:
            logging.info("Next transition not found")
            return None
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


def read_push_analytics():
    logging.info('Reading push analytics...')
    spreadsheet_id = '1-2szkn5ZE1E1CUoH5iOGKj-eJ003sC-o6ykaHapH0TA'
    range_name = 'Check!A3:L'
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values')

    if not values:
        return None

    row = values[0]

    result = {}

    if len(row) > 0 and row[0]:
        result['date'] = row[0]

    if len(row) > 1 and row[1]:
        result['delivered_android'] = row[1]

    if len(row) > 2 and row[2]:
        result['delivered_ios'] = row[2]

    if len(row) > 3 and row[3]:
        result['sent_android'] = row[3]

    if len(row) > 4 and row[4]:
        result['sent_ios'] = row[4]

    if len(row) > 5 and row[5]:
        result['with_error_android'] = row[5]

    if len(row) > 6 and row[6]:
        result['with_error_ios'] = row[6]

    if len(row) > 7 and row[7]:
        result['duplicated_with_sms_android'] = row[7]

    if len(row) > 8 and row[8]:
        result['duplicated_with_sms_ios'] = row[8]

    if len(row) > 9 and row[9]:
        result['saved_bank'] = row[9]

    if len(row) > 10 and row[10]:
        result['сonnected_clients'] = row[10]

    if len(row) > 11 and row[11]:
        result['disconnected_clients'] = row[11]

    if len(row) > 12 and row[12]:
        result['updated_push_tokens'] = row[12]

    return result


class TaskUploaderException(BaseException):
    pass


if __name__ == "__main__":
    try:
        handle_transitions(CHAT_ID)
        upload_data(to_data_json(chat_id=CHAT_ID, tasks=to_sort_tasks(to_group_tasks(get_tasks(get_active_sprint_id()))),
                                 push_analytics=read_push_analytics()))
    except TaskUploaderException as ex:
        logging.error(ex)
    except BaseException as ex:
        logging.exception(ex)
