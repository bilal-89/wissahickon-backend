import uuid
from datetime import datetime

def generate_uuid():
    return str(uuid.uuid4())

def format_datetime(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def parse_datetime(dt_str):
    return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%SZ')
