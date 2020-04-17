"""Call back handler to post message"""
import datetime
import json
import logging.config
import os
import random
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
    if event.get('source') == 'aws.events':
        return handle_scheduled_event()

    return handle_api_event(event)


def handle_scheduled_event():
    lines = list()
    incoming_text = "scheduled event"
    with open(f'phrases/madden_cloudwatch.txt', 'r') as phrases_file:
        lines.extend(phrases_file.readlines())
    text = lines[random.choice(lines)]
    post_to_group_and_save(incoming_text, text)
    return {'message': ''}


def post_to_group_and_save(incoming_text, outgoing_text):
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


def handle_api_event(event):
    request_payload = json.loads(event['body'])
    LOGGER.info(f'Message: {request_payload}')
    sender_id = request_payload['sender_id']
    if sender_id == '26901603':
        return copy_paste_message(request_payload)
    if sender_id == '6997876':
        return handle_text_files(request_payload, 'brian.txt')
    return handle_text_files(request_payload, 'madden.txt')


def copy_paste_message(request_payload: dict) -> dict:
    # let's provide a 33% chance for copying pasting messages so it's not spam
    # it could be random.choice([1, 2, 3]) == 3 but i didn't feel like doing that
    if random.choice([1, 2, 3, 4, 5, 6]) % 3 == 0:
        incoming_text = request_payload.get('text', '')
        post_to_group_and_save(incoming_text, incoming_text)
        return {'message': 'copied message'}

    return {'message': 'did not copy message'}


def handle_text_files(request_payload: dict, text_file: str) -> dict:
    incoming_text = request_payload.get('text', '')
    LOGGER.info(f'Message: {request_payload}')
    outgoing_text = find_outgoing_text(incoming_text, request_payload, text_file)
    if outgoing_text:
        text = outgoing_text if text_file != 'brian.txt' else f'What Detroit is really saying is...\n\n{outgoing_text}'
        post_to_group_and_save(incoming_text, text)
        return {'message': 'translated the phrase'}

    return {'message': 'no phrase found to translate'}


def find_outgoing_text(incoming_text: str, request_payload: dict, text_file: str) -> str:
    lines = list()
    with open(f'phrases/{text_file}', 'r') as phrases_file:
        lines.extend(phrases_file.readlines())

    if not lines:
        LOGGER.warning('Failure to read file')
        return ''

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

    return ''


def build_phrases(lines: list) -> dict:
    phrases = dict()
    for line in lines:
        phrase = line.split(',')
        if '_' in phrase:
            responses = phrase.split('_')
            phrases.update({phrase[0]: random.choice(responses)})
        else:
            phrases.update({phrase[0]: phrase[1].strip()})

    return phrases


def calculate_match_percentage(expected_phrase: str, incoming_text: str, request_payload: dict) -> float:
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
