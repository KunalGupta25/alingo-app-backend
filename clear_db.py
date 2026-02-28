import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from database.mongo import get_users_collection, get_rides_collection, get_reviews_collection

def clear_db():
    print("Clearing database...")
    users = get_users_collection()
    rides = get_rides_collection()
    reviews = get_reviews_collection()
    
    # Delete all documents in these collections
    u_result = users.delete_many({})
    print(f"Deleted {u_result.deleted_count} users.")
    
    r_result = rides.delete_many({})
    print(f"Deleted {r_result.deleted_count} rides.")
    
    rev_result = reviews.delete_many({})
    print(f"Deleted {rev_result.deleted_count} reviews.")
    
    print("Database cleared successfully.")

if __name__ == "__main__":
    clear_db()
