"""
Push Notification Utility — Expo Push Notifications
Sends notifications via Expo's push service (https://exp.host/--/api/v2/push/send).
No FCM/APNs configuration required for Expo Go / dev builds.
"""
import requests
from bson import ObjectId
from database.mongo import get_users_collection

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'


def send_push_notification(user_id, title: str, body: str, data: dict = None):
    """
    Send a push notification to a single user.
    Silently skips if the user has no stored push token.
    """
    try:
        users = get_users_collection()
        user = users.find_one(
            {'_id': ObjectId(user_id) if isinstance(user_id, str) else user_id},
            {'expo_push_token': 1}
        )
        token = (user or {}).get('expo_push_token')
        if not token:
            return

        message = {
            'to': token,
            'sound': 'default',
            'title': title,
            'body': body,
            'data': data or {},
        }

        resp = requests.post(
            EXPO_PUSH_URL,
            json=message,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=10,
        )
        print(f'[PUSH] Sent to {user_id}: {resp.status_code}')
    except Exception as e:
        print(f'[PUSH ERROR] {e}')


def send_bulk_notifications(user_ids, title: str, body: str, data: dict = None):
    """
    Send push notifications to multiple users in a single batch request.
    Filters out users without stored push tokens.
    """
    try:
        users = get_users_collection()
        oids = [ObjectId(uid) if isinstance(uid, str) else uid for uid in user_ids]

        docs = users.find(
            {'_id': {'$in': oids}, 'expo_push_token': {'$exists': True, '$ne': ''}},
            {'expo_push_token': 1}
        )

        messages = []
        for doc in docs:
            token = doc.get('expo_push_token')
            if token:
                messages.append({
                    'to': token,
                    'sound': 'default',
                    'title': title,
                    'body': body,
                    'data': data or {},
                })

        if not messages:
            return

        resp = requests.post(
            EXPO_PUSH_URL,
            json=messages,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=15,
        )
        print(f'[PUSH BULK] Sent {len(messages)} notifications: {resp.status_code}')
    except Exception as e:
        print(f'[PUSH BULK ERROR] {e}')
