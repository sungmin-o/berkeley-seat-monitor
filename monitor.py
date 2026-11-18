"""Serverless public Berkeley class-page monitor. Python 3.12+, no dependencies."""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class SafeError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(url, payload=None, headers=None, method=None, retry=False):
    """Never expose exception URLs (Telegram embeds its token in the URL)."""
    for attempt in range(3 if retry else 1):
        try:
            req = Request(url, data=None if payload is None else json.dumps(payload).encode(),
                          headers={"User-Agent": "BerkeleySeatMonitor/1.0", "Content-Type": "application/json", **(headers or {})},
                          method=method)
            with build_opener(NoRedirect).open(req, timeout=25) as response:
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise SafeError("Response too large")
                return data
        except HTTPError as exc:
            status = exc.code
            if retry and status in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise SafeError(f"HTTP {status}") from None
        except (URLError, TimeoutError, OSError):
            if retry and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise SafeError("Network error/timeout") from None


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def parse_page(html, section):
    parser = Text()
    parser.feed(html)
    text = re.sub(r'\s+', ' ', ' '.join(parser.parts))
    if not re.search(r'Class\s*#\s*:\s*' + re.escape(section['class_number']) + r'\b', text):
        raise SafeError("Class number missing/mismatch")
    if section['term'].casefold() not in text.casefold() or section['course'].casefold() not in text.casefold():
        raise SafeError("Course/term missing/mismatch")
    # Only the first enrollment block: never use another section's counts.
    block = text.split('Current Enrollment', 1)
    if len(block) != 2:
        raise SafeError("Enrollment block missing; site may have changed")
    block = re.split(r'Hours & Workload|Reserved Seats|Textbooks|Associated Sections|Current Enrollment', block[1])[0]
    values = {}
    for label in ('Total Open Seats', 'Enrolled', 'Waitlisted', 'Capacity'):
        matches = re.findall(re.escape(label) + r'\s*:\s*(-?\d[\d,]*)\b', block)
        if len(matches) != 1:
            raise SafeError("Enrollment fields missing/ambiguous")
        values[label] = int(matches[0].replace(',', ''))
    if any(values[k] < 0 for k in ('Enrolled', 'Waitlisted', 'Capacity')):
        raise SafeError("Invalid enrollment counts")
    return values


def load_config(path):
    sections = json.loads(Path(path).read_text())['sections']
    if not 1 <= len(sections) <= 20:
        raise SafeError("Configure 1–20 sections")
    keys = set()
    for s in sections:
        u = urlsplit(s['url'])
        if u.scheme != 'https' or u.netloc != 'classes.berkeley.edu' or u.query or u.fragment or not u.path.startswith(('/content/', '/node/')):
            raise SafeError("Use an HTTPS classes.berkeley.edu detail URL")
        if not re.fullmatch(r'\d{5}', s['class_number']) or not s['term'] or not s['course']:
            raise SafeError("Invalid section identity")
        if type(s['min_open_seats']) is not int or s['min_open_seats'] < 1:
            raise SafeError("min_open_seats must be a positive integer")
        capacity = s.get('waitlist_capacity')
        if capacity is not None and (type(capacity) is not int or capacity < 0):
            raise SafeError("waitlist_capacity must be a nonnegative integer or null")
        key = identity(s)
        if key in keys:
            raise SafeError("Duplicate section")
        keys.add(key)
    return sections


def identity(s):
    return hashlib.sha256(json.dumps({k: v for k, v in s.items() if k != 'waitlist_capacity'}, sort_keys=True).encode()).hexdigest()


class State:
    """Durable state on default branch, using GitHub's SHA compare-and-swap."""
    def __init__(self):
        repo = os.environ['GITHUB_REPOSITORY']
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
            raise SafeError("Invalid repository")
        self.url = f'https://api.github.com/repos/{repo}/contents/monitor-state.json'
        self.headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json'}
        result = json.loads(request(self.url, headers=self.headers, retry=True))
        self.sha = result['sha']
        self.data = json.loads(base64.b64decode(result['content']))
        if self.data.get('version') != 1 or not isinstance(self.data.get('sections'), dict):
            raise SafeError("Invalid persisted state; refusing reset")

    def save(self):
        content = base64.b64encode((json.dumps(self.data, indent=2) + '\n').encode()).decode()
        result = json.loads(request(self.url, {'message': 'Update seat monitor state', 'sha': self.sha, 'content': content}, self.headers, 'PUT'))
        self.sha = result['content']['sha']


def telegram(message):
    result = json.loads(request('https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN'] + '/sendMessage',
                                {'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'text': message, 'link_preview_options': {'is_disabled': True}}))
    if result.get('ok') is not True:
        raise SafeError("Telegram delivery rejected")


def should_alert(previous, seats, threshold):
    return seats >= threshold and previous is not True


def check_waitlist(section, values, state):
    # Explicit, user-verified waitlist capacity; class Capacity is NOT waitlist capacity.
    capacity = section.get('waitlist_capacity')
    if capacity is None:
        print('Waitlist alert disabled: capacity not configured')
        return
    available = max(0, capacity - values['Waitlisted'])
    print(f'Waitlist available={available} (configured capacity={capacity})')
    if state is None:
        return
    key = 'waitlist:' + identity(section) + ':' + str(capacity)
    previous = state.data['sections'].get(key)
    opened = available > 0
    if should_alert(previous, available, 1):
        telegram(f'대기명단 여유 감지: {section["term"]} {section["course"]}\n'
                 f'Class # {section["class_number"]}\n'
                 f'대기 인원: {values["Waitlisted"]} / 설정한 대기 정원: {capacity}\n'
                 f'계산된 대기명단 여유: {available}\n'
                 f'설정한 정원 기준입니다. 실제 신청 가능 여부는 CalCentral에서 확인하세요.\n{section["url"]}')
    if previous is not opened:
        state.data['sections'][key] = opened
        state.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config.json')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--test-telegram', action='store_true')
    args = ap.parse_args()
    if args.test_telegram:
        telegram('Berkeley seat monitor: Telegram 연결 성공. 이 메시지는 빈자리 알림이 아닙니다.')
        return 0
    sections = load_config(args.config)
    state = None if args.dry_run else State()
    errors = 0
    for index, s in enumerate(sections, 1):
        try:
            values = parse_page(request(s['url'], retry=True).decode('utf-8'), s)
            seats = values['Total Open Seats']
            print(f'Section {index}: open={seats}, enrolled={values["Enrolled"]}, waitlisted={values["Waitlisted"]}')
            if state is None:
                check_waitlist(s, values, None)
                continue
            key = identity(s)
            previous = state.data['sections'].get(key)
            opened = seats >= s['min_open_seats']
            if should_alert(previous, seats, s['min_open_seats']):
                telegram(f'빈자리 감지: {s["term"]} {s["course"]}\nClass # {s["class_number"]}\n공개 총 빈자리: {seats}\n대기 인원: {values["Waitlisted"]}\n예약석/수강 조건은 CalCentral에서 확인하세요.\n{s["url"]}')
            if previous is not opened:
                state.data['sections'][key] = opened
                state.save()
            check_waitlist(s, values, state)
        except (SafeError, ValueError, KeyError, UnicodeError) as exc:
            # Do not print server bodies, URLs, tokens, chat IDs, or raw exceptions.
            print(f'Section {index}: check/delivery/state failed; inspect source access and configuration.', file=sys.stderr)
            if isinstance(exc, SafeError):
                print(f'Reason: {exc}', file=sys.stderr)
            errors += 1
        if index < len(sections):
            time.sleep(1)
    return 1 if errors else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (SafeError, ValueError, KeyError, OSError):
        print('Monitor initialization failed; verify config, secrets, and state permissions.', file=sys.stderr)
        sys.exit(1)
