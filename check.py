import argparse
import base64
import os
import re
import sys
import types

try:
    import settings
except ImportError:
    settings = types.SimpleNamespace()
    settings.USERNAME = ''
    settings.TOKEN = ''
import requests

USERNAME = os.environ.get('GITHUB_USERNAME', getattr(settings, 'USERNAME'))
TOKEN = os.environ.get('GITHUB_TOKEN', getattr(settings, 'TOKEN'))

# For token generation, login into GitHub > Settings > Developer settings > Personal access tokens
# > Tokens (classic) > Generate new token > (classic)
# Needs the following permissions (maybe less, I have not read up on this yet):
# - repo
# - read:org


headers = {
    'Accept': 'application/vnd.github+json'
}


def get_issue(repo_url):
    match = re.search(r'^https://github.com/(.+)/(.+)', repo_url)
    if match:
        owner, repo = match.groups()
        response = requests.get(f'https://api.github.com/repos/{owner}/{repo}/issues/1',
                                headers=headers, auth=(USERNAME, TOKEN), timeout=15)
        if response.status_code == 200:
            return response.json()
        return None
    raise ValueError('Invalid url')


def get_badges(repo_url):
    match = re.search(r'^https://github.com/(.+)/(.+)', repo_url)
    if match:
        owner, repo = match.groups()
        response = requests.get(
            f'https://api.github.com/repos/{owner}/{repo}/contents/.github/badges/points.svg?ref=badges',
            headers=headers, auth=(USERNAME, TOKEN), timeout=15)
        if response.status_code == 200:
            return response.json()
        return None
    raise ValueError('Invalid url')


def parse_issue(issue):
    match = re.search(r'^Punkte: (\d+/\d+).*', issue.get('body', ''))
    if match:
        data = match.group().strip()
        point_match = re.search(r'^Punkte: (\d+)/(\d+)$', data)
        return point_match.groups()
    raise ValueError('Invalid Issue')


def parse_badge(badge_file):
    file_content = badge_file.get('content', '')
    file_content_encoding = badge_file.get('encoding', '')
    if file_content_encoding == 'base64':
        file_content = base64.b64decode(file_content).decode()

        match = re.search(r'<title>Voraussichtliche Punktzahl: (\d+) / (\d+)</title>', file_content)
        if match:
            return match.groups()
    raise ValueError('Invalid Badge')


def check_file(filename, **kwargs):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            for line in file.readlines():
                line = line.strip()
                if line.startswith('*'):
                    match = re.search(r'(https://github.com/\S*).*$', line)
                    if match:
                        check_repo(match.groups()[0], **kwargs)
    except FileNotFoundError as e:
        print('ERROR: File does not exist', file=sys.stderr)
        print(e, file=sys.stderr)
    except PermissionError as e:
        print('ERROR: Could not open file', file=sys.stderr)
        print(e, file=sys.stderr)


def check_repo(repo_url, manual, badge_override):
    try:
        issue = get_issue(repo_url)
        if issue:
            issue_given, issue_max = parse_issue(issue)
            if not badge_override:
                badge = get_badges(repo_url)
                if badge:
                    badge_given, badge_max = parse_badge(badge)
                else:
                    print(f'CRITICAL: Repo {repo_url} has NO badge')
                    return
            else:
                badge_given, badge_max = badge_override, badge_override
            if int(issue_max) != (int(badge_max) + manual):
                print(f'CRITICAL: Repo {repo_url} has '
                      f'different max points, issue is {issue_max}, badge is {badge_max} + {manual} (manual)')
            if int(issue_given) != int(badge_given) + manual:
                print(f'WARNING: Repo {repo_url} has '
                      f'different given points, issue is {issue_given}, badge is {badge_given} + {manual} (manual)')
            print(f'NOTICE: Finished checking {repo_url}')
        else:
            print(f'CRITICAL: Repo {repo_url} has NO issue')
    except ValueError as e:
        print(f'ERROR: Could not parse {repo_url}', file=sys.stderr)
        print(e, file=sys.stderr)


def check_login():
    response = requests.get(f'https://api.github.com/user', headers=headers, auth=(USERNAME, TOKEN), timeout=15)
    if response.status_code != 200:
        raise ConnectionError()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='Progra Checker')
    parser.add_argument('filename')
    parser.add_argument('-m', '--manual', type=int, default=0,
                        help='If parts of the correction are manual enter the points for it here')
    parser.add_argument('-b', '--badge-override', type=int, dest='badge_override',
                        help='Override badge', default=None)
    args = parser.parse_args()
    try:
        check_login()
    except ConnectionError as e:
        print("ERROR: Could not connect to github with given credentials", file=sys.stderr)
        sys.exit(1)

    check_file(**vars(args))
