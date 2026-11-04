import unittest
import korean_listings as kl


def snapshot():
    rows = []
    for market, base, count in [('코스피', 100000, 500), ('코스닥', 200000, 500), ('코넥스', 300000, 20)]:
        rows.extend({'name': f'회사{i}', 'code': str(base+i), 'exchange': market} for i in range(count))
    return {'updated_at': 100000, 'rows': rows}


class DirectoryTests(unittest.TestCase):
    def test_parse_encoding_and_leading_zero(self):
        html = '<table><tr><th>회사명</th><th>종목코드</th></tr><tr><td>LG전자</td><td>066570</td></tr></table>'
        for encoding in ['utf-8', 'cp949']:
            self.assertEqual(kl.parse_listing(html.encode(encoding), '코스피'),
                             [{'name': 'LG전자', 'code': '066570', 'exchange': '코스피'}])
        with self.assertRaises(ValueError):
            kl.parse_listing(b'<html>blocked</html>', '코스피')

    def test_partial_directory_rejected(self):
        data = snapshot()
        kl.validate_snapshot(data)
        data['rows'] = data['rows'][:500]
        with self.assertRaises(ValueError):
            kl.validate_snapshot(data)
