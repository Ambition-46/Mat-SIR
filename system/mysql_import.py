"""Initialize smart_small from the supplied MySQL dump and enable uploads."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

import pymysql
from sql.settings import get_mysql_conf

DUMP = Path(__file__).resolve().parents[1] / 'database/smart_small.sql'
CORE = {'property_table', 'entity_table', 'value_table'}
AUXILIARY = (
    """CREATE TABLE IF NOT EXISTS matsir_property_unit(
        property_name VARCHAR(100) PRIMARY KEY,standard_unit VARCHAR(100) NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS matsir_source(
        dataset VARCHAR(100) NOT NULL,source_id VARCHAR(255) NOT NULL,data_id BIGINT UNSIGNED UNIQUE,
        PRIMARY KEY(dataset,source_id),FOREIGN KEY(data_id) REFERENCES entity_table(data_id))""",
    """CREATE TABLE IF NOT EXISTS matsir_history(
        property_id BIGINT UNSIGNED PRIMARY KEY,FOREIGN KEY(property_id) REFERENCES property_table(property_id))""",
    """CREATE TABLE IF NOT EXISTS matsir_field(
        data_id BIGINT UNSIGNED NOT NULL,field VARCHAR(255) NOT NULL,description TEXT NOT NULL,
        unit VARCHAR(100) NOT NULL,raw_value TEXT NOT NULL,property_name VARCHAR(100),role VARCHAR(10),
        PRIMARY KEY(data_id,field),UNIQUE(data_id,property_name),FOREIGN KEY(data_id) REFERENCES entity_table(data_id))""",
)


def initialize(restore=False):
    conf=get_mysql_conf()
    if restore:
        server_conf={k:v for k,v in conf.items() if k!='database'}
        with pymysql.connect(**server_conf) as conn, conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS smart_small CHARACTER SET utf8mb4")
    with pymysql.connect(**conf) as conn, conn.cursor() as cur:
        cur.execute("SELECT GET_LOCK('matsir_install_smart_small',30)")
        if cur.fetchone()[0]!=1: raise RuntimeError('Database installation already in progress')
        cur.execute('SHOW TABLES')
        tables={r[0] for r in cur.fetchall()}
        if not tables and restore:
            client=shutil.which('mysql') or '/usr/local/mysql/bin/mysql'
            with DUMP.open('rb') as source:
                subprocess.run([client,'--no-defaults','--protocol=TCP','--default-character-set=utf8mb4',
                                '-h',conf['host'],'-P',str(conf['port']),'-u',conf['user'],'smart_small'],
                               stdin=source,env=dict(os.environ,MYSQL_PWD=conf['password']),check=True)
        elif not CORE.issubset(tables):
            raise RuntimeError('Import database/smart_small.sql into an empty smart_small database first')
        for ddl in AUXILIARY: cur.execute(ddl)


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--question')
    cli.add_argument('--online',action='store_true')
    args=cli.parse_args()
    initialize(restore=True)
    if args.question:
        from .service import connect,query
        with connect() as db:
            print(json.dumps(query(db,args.question,args.online),ensure_ascii=False))
