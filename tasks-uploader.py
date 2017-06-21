import traceback
import requests
import json
import operator
import sys

CHAT_ID = '-243322379'
BOARD_ID = '5046'
JIRA_USER_NAME = ''
JIRA_USER_PASSWORD = ''
GET_SPRINT_ID_URL = 'http://jira/rest/agile/1.0/board/{board_id}/sprint?state=active'
SPRINT_TASK_STATUSES = 'BACKLOG, DONE'
GET_SPRINT_TASKS_URL = 'http://jira/rest/agile/1.0/board/{board_id}/sprint/{sprint_id}/issue?jql=status in ({' \
                       'task_statuses}) AND ' \
                       'type=sub-task&fields=summary,assignee,issuetype,status,parent,resolution'
TASKS_UPLOAD_URL = 'https://wb9fbkheca.execute-api.us-east-2.amazonaws.com/v0/upload'


def get_active_sprint_id():
    try:
        print('Getting sprint_id...')
        url = GET_SPRINT_ID_URL.format(board_id=BOARD_ID)
        response = requests.get(url=url, auth=(JIRA_USER_NAME, JIRA_USER_PASSWORD))
        if 'values' not in response.json():
            return None
        values = response.json()['values']
        if not values:
            return None
        sprint_id = values[0]['id']
        show_response_result(response)
        return sprint_id
    except Exception:
        print(traceback.format_exc())


def get_tasks(sprint_id):
    try:
        print('Getting tasks...')
        url = GET_SPRINT_TASKS_URL.format(board_id=BOARD_ID, sprint_id=sprint_id, task_statuses=SPRINT_TASK_STATUSES)
        response = requests.get(url=url, auth=(JIRA_USER_NAME, JIRA_USER_PASSWORD))
        task_list = []
        for task in response.json()['issues']:
            task_item = TaskItem()
            if 'key' in task:
                task_item.key = task['key']
            if 'fields' in task:
                fields = task['fields']
                if 'summary' in fields:
                    task_item.summary = fields['summary']
                if 'assignee' in fields:
                    if fields['assignee'] is not None:
                        task_item.assignee_display_name = fields['assignee'].get('displayName', None)
                if 'issuetype' in fields:
                    if fields['issuetype'] is not None:
                        task_item.issue_type_description = fields['issuetype'].get('description', None)
                if 'parent' in fields:
                    if fields['parent'] is not None:
                        parent = fields['parent']
                        task_item.parent_key = parent.get('key', None)
                        if parent['fields'] is not None:
                            task_item.parent_summary = parent['fields'].get('summary', None)
                if 'resolution' in fields:
                    task_item.resolution = fields['resolution']
                if 'status' in fields:
                    if fields['status'] is not None:
                        task_item.status_name = fields['status'].get('name', None)

            task_list.append(task_item)
        show_response_result(response)
        return task_list
    except Exception:
        print(traceback.format_exc())


def task_list_to_json(task_list, chat_id):
    dictionary = dict()
    dictionary['chat_id'] = chat_id
    for task in task_list:
        dictionary.setdefault('tasks', []).append(task.__dict__)

    return json.dumps(dictionary)


def upload_tasks(tasks_json):
    try:
        print('Uploading tasks...')
        response = requests.post(url=TASKS_UPLOAD_URL, data=tasks_json)
        if response.json() is not None and 'errorMessage' in response.json():
            raise Exception(response.json())
        show_response_result(response)
    except Exception:
        print(traceback.format_exc())


def show_response_result(response):
    if response.status_code == requests.codes.ok:
        print('Done.')
    else:
        print(response.json())


class TaskItem:
    pass


if __name__ == "__main__":
    active_sprint_id = get_active_sprint_id()
    if not active_sprint_id:
        print('Active Sprint not found.')
        sys.exit(0)
    tasks = get_tasks(active_sprint_id)
    tasks.sort(key=operator.attrgetter('status_name'), reverse=False)
    upload_tasks(task_list_to_json(tasks, CHAT_ID))
