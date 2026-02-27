import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from database.mongo import get_users_collection

users_col = get_users_collection()
users = users_col.find().sort('_id', -1).limit(5)

print("--- Latest 5 Users in DB ---")
for u in users:
    print(f"UID: {u.get('uid')}")
    print(f"Phone: {u.get('phone')}")
    print(f"Name: {u.get('full_name', '<missing>')}")
    print(f"Age: {u.get('age', '<missing>')}")
    print(f"Gender: {u.get('gender', '<missing>')}")
    print("----------------------------")
