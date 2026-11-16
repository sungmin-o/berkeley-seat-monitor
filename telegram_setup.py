"""Local helper: hidden token entry, prints only private chat IDs, no message text."""
import getpass
import json
from monitor import request, SafeError

if __name__ == '__main__':
    token = getpass.getpass('BotFather token (hidden): ').strip()
    try:
        result = json.loads(request('https://api.telegram.org/bot' + token + '/getUpdates'))
        if result.get('ok') is not True:
            raise SafeError('Telegram rejected request')
        ids = {u['message']['chat']['id'] for u in result['result']
               if u.get('message', {}).get('chat', {}).get('type') == 'private'}
        if ids:
            for chat_id in sorted(ids):
                print('Private chat ID:', chat_id)
        else:
            print('No private messages found. Start the bot and send a message first.')
    except (SafeError, ValueError, KeyError):
        print('Setup failed. Check token/network; use a dedicated bot without a webhook.')
        raise SystemExit(1)
