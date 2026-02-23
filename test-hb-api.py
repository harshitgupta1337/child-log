import time
from huckleberry_api import HuckleberryAPI

timezone="America/New_York"

# Initialize API client
api = HuckleberryAPI(
    email="harshitgupta1337@gmail.com",
    password="Pritha@BWH2026",
    timezone=timezone,
)

# Authenticate
api.authenticate()

# Get children
children = api.get_children()
child_uid = children[0]["uid"]

print (children[1])

api.log_diaper_at_time(
  child_uid,
  mode="poo",
  poo_amount="big",
  color="yellow",
  consistency="solid",
  time_ms=time.time())
