import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from database.mongo import get_rides_collection
import pprint

rides = get_rides_collection()
print("--- INDEXES ---")
pprint.pprint(rides.index_information())

print("\n--- SAMPLE RIDE ---")
ride = rides.find_one({})
pprint.pprint(ride)
