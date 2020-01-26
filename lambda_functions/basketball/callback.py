"""Call back handler to post message"""
import datetime
import json
import logging.config
import os

import boto3
import requests


BOT_ID = os.environ['BOT_ID']
BOT_POSTS_TABLE_NAME = os.environ['BOT_POSTS_TABLE_NAME']
BOT_POSTS_TABLE = boto3.resource('dynamodb').Table(BOT_POSTS_TABLE_NAME)
GROUPME_URL = os.environ['GROUPME_URL']
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def handler(event, context):
    LOGGER.info('received request')
    if is_post_sent_for_day():
        # Return early, message already sent for the day
        LOGGER.info('Message already sent for the day')
        return {'message': 'already posted'}

    request_payload = json.loads(event['body'])
    LOGGER.info(f'Message: {request_payload.get("text", "")}')

    if is_ball_tonight_message(request_payload):
        LOGGER.info('claiming spot')
        payload = {
            "bot_id": BOT_ID,
            "text": "In"
        }

        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.post(GROUPME_URL, headers=headers, json=payload)
        response.raise_for_status()

        save_to_dynamo(payload)


def is_ball_tonight_message(request_payload):
    message_words = request_payload.get('text', '').lower().split(' ')
    return 'ball' in message_words and 'tonight' in message_words and 'in' in message_words


def is_post_sent_for_day():
    return bool(BOT_POSTS_TABLE.get_item(Key={
        'date': datetime.datetime.now().strftime('%Y-%m-%d'),
        'group': 'basketball'
    }).get('Item'))


def save_to_dynamo(payload):
    LOGGER.info('Saving message')
    BOT_POSTS_TABLE.put_item(Item={
        'date': datetime.datetime.now().strftime('%Y-%m-%d'),
        'group': 'basketball',
        'request_payload': json.dumps(payload)
    })
