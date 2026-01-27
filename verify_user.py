"""
Quick script to verify a user account
Run this to manually verify users during development
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from database.mongo import get_users_collection

def list_users():
    """List all users in the database"""
    users = get_users_collection()
    all_users = list(users.find())
    
    print("\n" + "="*60)
    print("ALL USERS IN DATABASE")
    print("="*60)
    
    if not all_users:
        print("No users found!")
        return
    
    for idx, user in enumerate(all_users, 1):
        print(f"\n{idx}. User:")
        print(f"   ID: {user['_id']}")
        print(f"   Phone: {user.get('phone', 'N/A')}")
        print(f"   Status: {user.get('verification_status', 'N/A')}")
        print(f"   Created: {user.get('created_at', 'N/A')}")
    
    print("\n" + "="*60)

def verify_user(phone_number):
    """Verify a user by phone number"""
    users = get_users_collection()
    
    # Find user
    user = users.find_one({'phone': phone_number})
    
    if not user:
        print(f"❌ User with phone {phone_number} not found!")
        return False
    
    # Update verification status
    result = users.update_one(
        {'phone': phone_number},
        {'$set': {'verification_status': 'VERIFIED'}}
    )
    
    if result.modified_count > 0:
        print(f"✅ User {phone_number} verified successfully!")
        return True
    else:
        print(f"⚠️ User already verified or update failed")
        return False

if __name__ == '__main__':
    print("\n🔐 User Verification Tool")
    print("-" * 60)
    
    # List all users first
    list_users()
    
    # Ask for phone number to verify
    print("\nEnter phone number to verify (with +, e.g., +1234567890)")
    print("Or press Enter to exit:")
    
    phone = input("> ").strip()
    
    if phone:
        verify_user(phone)
        print("\n")
        list_users()
    else:
        print("Exiting...")
