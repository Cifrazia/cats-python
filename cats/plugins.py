try:
    from django.db.models import QuerySet
except ImportError:
    QuerySet = type('QuerySet', (list,), {})

try:
    from rest_framework.serializers import BaseSerializer
except ImportError:
    BaseSerializer = type('BaseSerializer', (object,), {})

__all__ = [
    'QuerySet',
    'BaseSerializer'
]
