"""Call back handler to post message"""
import datetime
import json
import logging.config
import os
import string

import boto3
import requests


BOT_ID = os.environ['BOT_ID']
BOT_POSTS_TABLE_NAME = os.environ['BOT_POSTS_TABLE_NAME']
BOT_POSTS_TABLE = boto3.resource('dynamodb').Table(BOT_POSTS_TABLE_NAME)
GROUPME_URL = os.environ['GROUPME_URL']
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def handler(event, context):
    request_payload = json.loads(event['body'])
    LOGGER.info(f'Message: {request_payload}')
    if request_payload['sender_id'] == '6997876':
        return handle_brian(request_payload)

    return {'message': 'do nothing, it aint brian'}


def handle_brian(request_payload):
    incoming_text = request_payload.get('text', '')
    LOGGER.info(f'Message: {request_payload}')
    outgoing_text = find_outgoing_text(incoming_text, request_payload)
    if outgoing_text:
        LOGGER.info('sending message')
        payload = {
            "bot_id": BOT_ID,
            "text": outgoing_text
        }

        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.post(GROUPME_URL, headers=headers, json=payload)
        response.raise_for_status()

        save_to_dynamo(incoming_text, outgoing_text)

        return {'message': 'translated the phrase'}

    return {'message': 'no phrase found to translate'}


def find_outgoing_text(incoming_text, request_payload):
    lines = list()
    with open('phrases/brian.txt', 'r') as phrases_file:
        lines.extend(phrases_file.readlines())

    if not lines:
        LOGGER.warning('Failure to read file')
        return None

    phrases = build_phrases(lines)

    phrase_match_percentages = dict()
    for expected_phrase, translated_phrase in phrases.items():
        if expected_phrase.lower().translate(str.maketrans('', '', string.punctuation)) == incoming_text.lower(
        ).translate(str.maketrans('', '', string.punctuation)):
            return translated_phrase

        phrase_match_percentages.update(
            {expected_phrase: calculate_match_percentage(expected_phrase, incoming_text, request_payload)})

        # sort percentages
        phrase_match_percentages = {k: v for k, v in
                                    sorted(phrase_match_percentages.items(), key=lambda item: item[1], reverse=True)}
        winner = list(phrase_match_percentages.items())[0]
        if winner[1] != 0:
            return phrases[winner[0]]

    return None


def build_phrases(lines):
    phrases = dict()
    for line in lines:
        phrase = line.split(',')
        phrases.update({phrase[0]: phrase[1].strip()})

    return phrases


def calculate_match_percentage(expected_phrase, incoming_text, request_payload):
    text = incoming_text
    if request_payload.get('type', '') == 'mentions':
        text = incoming_text[:incoming_text['@']].strip()

    expected_words = set(expected_phrase.lower().translate(str.maketrans('', '', string.punctuation)).split(' '))
    incoming_words = set(text.lower().translate(str.maketrans('', '', string.punctuation)).split(' '))
    percentage = len(expected_words.intersection(incoming_words)) / len(incoming_words) * 100
    if 80 <= percentage < 100:
        return percentage

    return 0.0


def save_to_dynamo(incoming_text, outgoing_text):
    LOGGER.info('Saving message')
    BOT_POSTS_TABLE.put_item(Item={
        'date': datetime.datetime.now().isoformat(),
        'group': 'madden',
        'incoming_text': incoming_text,
        'outgoing_text': outgoing_text
    })
