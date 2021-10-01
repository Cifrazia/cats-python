from pytest import mark

from cats.v3.scheme import JSON


class TestJsonScheme:
    @mark.parametrize('buff, data', (
            ('null', None),
            ('1', 1),
            ('2.3', 2.3),
            ('true', True),
            ('false', False),
            ('"Hello"', 'Hello'),
            ('[1,2,3]', [1, 2, 3]),
            ('{"a": [1,2,3]}', {'a': [1, 2, 3]}),
            (b'"bytes"', 'bytes')
    ))
    def test_loads(self, buff, data):
        assert JSON.loads(buff) == data
