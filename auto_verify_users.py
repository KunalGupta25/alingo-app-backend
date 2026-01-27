"""
Auto-verify all PENDING users
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from database.mongo import get_users_collection

users_collection = get_users_collection()

# Find all pending users
pending_users = list(users_collection.find({'verification_status': 'PENDING'}))

print(f"\nFound {len(pending_users)} PENDING users:")
print("=" * 60)

for user in pending_users:
    print(f"\n📱 Phone: {user.get('phone')}")
    print(f"   Status: {user.get('verification_status')}")
    print(f"   Created: {user.get('created_at')}")
    
    # Verify this user
    result = users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {'verification_status': 'VERIFIED'}}
    )
    
    if result.modified_count > 0:
        print(f"   ✅ VERIFIED!")
    else:
        print(f"   ⚠️  Failed to verify")

print("\n" + "=" * 60)
print("✅ All users verified!")
print("\nYou can now log in to the app.")
