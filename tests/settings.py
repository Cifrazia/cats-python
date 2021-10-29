import logging

logging.basicConfig(level='DEBUG', force=True)
SECRET_KEY = b'top_secret'
DEBUG = True
INSTALLED_APPS = [
    'django.contrib.sites',
]
DATABASES = {}
