import logging
import os
from logging.config import dictConfig

LOG_LEVEL = 'DEBUG'
ECHO = True

LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'}
    },
    'handlers': {
        'stream': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': LOG_LEVEL
        },
        'file': {
            'level': LOG_LEVEL,
            'class': 'logging.FileHandler',
            'filename': os.environ.get('LOG_FILE', os.path.join(os.path.dirname(__file__),'mailapp.log')),
            'formatter': 'default',
        },
    },
    'root': {
        'handlers': ['stream','file'],
        'level': LOG_LEVEL,
    },
}

dictConfig(LOGGING_CONFIG)
logger = logging.getLogger()