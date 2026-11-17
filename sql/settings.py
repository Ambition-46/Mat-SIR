import os

def get_mysql_conf():
    if os.getenv('MYSQL_DATABASE', 'smart_small') != 'smart_small':
        raise ValueError('MYSQL_DATABASE must be smart_small')
    return dict(host=os.getenv('MYSQL_HOST','127.0.0.1'), port=int(os.getenv('MYSQL_PORT','3306')),
                user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'],
                database='smart_small', charset='utf8mb4')
