import unittest
from unittest.mock import patch
from urllib.error import URLError
import monitor

SECTION = {'term': '2026 Fall', 'course': 'PHYSICS 137B', 'class_number': '23064'}


def page(seats='3'):
    # Synthetic contract fixture, NOT a captured live page.
    return f'''<h1>2026 Fall PHYSICS 137B 001</h1><p>Class #:23064</p>
    <h3>Current Enrollment</h3><div>Total Open Seats: <b>{seats}</b></div>
    <p>Enrolled: 67</p><p>Waitlisted: 0</p><p>Capacity: 70</p>
    <h3>Hours &amp; Workload</h3><p>Current Enrollment Total Open Seats: 999</p>'''


class Tests(unittest.TestCase):
    def test_enrollment_block_scoping(self):
        self.assertEqual(monitor.parse_page(page(), SECTION)['Total Open Seats'], 3)

    def test_waitlist_independent_and_reopens(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        section = {**SECTION, 'url': 'https://classes.berkeley.edu/node/522854',
                   'min_open_seats': 1, 'waitlist_capacity': 10}
        original = {k: v for k, v in section.items() if k != 'waitlist_capacity'}
        self.assertEqual(monitor.identity(section), monitor.identity(original))
        state = SimpleNamespace(data={'sections': {monitor.identity(section): True}}, save=Mock())
        with patch('monitor.telegram') as send:
            for count in (10, 9, 8, 10, 9):
                monitor.check_waitlist(section, {'Waitlisted': count}, state)
            self.assertEqual(send.call_count, 2)
            self.assertTrue(state.data['sections'][monitor.identity(section)])

    def test_waitlist_missing_capacity_and_failed_delivery(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        section = {**SECTION, 'url': 'https://classes.berkeley.edu/node/522854'}
        state = SimpleNamespace(data={'sections': {}}, save=Mock())
        with patch('monitor.telegram') as send:
            monitor.check_waitlist(section, {'Waitlisted': 0}, state)
            send.assert_not_called()
        section['waitlist_capacity'] = 10
        with patch('monitor.telegram', side_effect=monitor.SafeError('delivery failed')):
            with self.assertRaises(monitor.SafeError):
                monitor.check_waitlist(section, {'Waitlisted': 9}, state)
        self.assertEqual(state.data['sections'], {})
        state.save.assert_not_called()

    def test_negative_seats(self):
        self.assertEqual(monitor.parse_page(page('-2'), SECTION)['Total Open Seats'], -2)

    def test_unknown_not_zero(self):
        for html in ('<h1>403 Forbidden</h1>', page().replace('Total Open Seats', 'Available'),
                     page().replace('23064', '23065'), page().replace('2026 Fall', '2027 Spring'),
                     page().replace('Enrolled: 67', 'Enrolled: 67 Enrolled: 66')):
            with self.subTest(html=html), self.assertRaises(monitor.SafeError):
                monitor.parse_page(html, SECTION)

    def test_duplicate_and_reopening(self):
        previous = None
        alerts = []
        for seats in (0, 1, 3, 0, 2):
            alerts.append(monitor.should_alert(previous, seats, 1))
            previous = seats >= 1
        self.assertEqual(alerts, [False, True, False, False, True])
        self.assertTrue(monitor.should_alert(None, 1, 1))

    def test_telegram_timeout_not_retried_or_leaked(self):
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'SECRET', 'TELEGRAM_CHAT_ID': 'PRIVATE'}), \
             patch('monitor.build_opener') as opener:
            opener.return_value.open.side_effect = URLError('https://api.telegram.org/botSECRET')
            with self.assertRaises(monitor.SafeError) as error:
                monitor.telegram('test')
            self.assertNotIn('SECRET', str(error.exception))
            self.assertEqual(opener.return_value.open.call_count, 1)

    def test_failed_delivery_keeps_state_and_checks_next_section(self):
        s = {**SECTION, 'url': 'https://classes.berkeley.edu/node/522854', 'min_open_seats': 1}
        with patch('sys.argv', ['monitor.py']), patch('monitor.load_config', return_value=[s]), \
             patch('monitor.State') as state, patch('monitor.request', return_value=page().encode()), \
             patch('monitor.telegram', side_effect=monitor.SafeError('delivery failed')):
            state.return_value.data = {'version': 1, 'sections': {}}
            self.assertEqual(monitor.main(), 1)
            self.assertEqual(state.return_value.data['sections'], {})
            state.return_value.save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
