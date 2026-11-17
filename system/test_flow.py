"""Integration test using a unique upload and cleaning up its rows."""
import json
import os
import unittest
import uuid
from pathlib import Path
from .mysql_import import initialize
from .service import connect, query, review, upload, full_rows


@unittest.skipUnless('MYSQL_USER' in os.environ,'requires a configured smart_small database')
class EndToEnd(unittest.TestCase):
    def test_import_restart_review_and_query(self):
        initialize()
        payload=json.loads(Path(__file__).with_name('example.json').read_text())
        dataset=payload['dataset']='test-'+uuid.uuid4().hex
        payload['records'][0]['fields'][1]['name']='Yield test'
        question='tensile_strength > 500 MPa AND yield_strength > 300 MPa'
        try:
            with connect() as db:
                self.assertEqual(upload(db,payload,False)['pending'],1)
                upload(db,payload,False)
            with connect() as db, db.cursor() as cur:
                self.assertFalse(any(r['dataset']==dataset for r in query(db,question,False)['records']))
                cur.execute("SELECT data_id FROM matsir_source WHERE dataset=%s AND source_id='sample-A'",(dataset,))
                eid=cur.fetchone()['data_id']
                review(db,dict(entity_id=eid,field='Yield test',property='yield_strength',description='屈服强度'))
                hits=[r for r in query(db,question,False)['records'] if r['dataset']==dataset]
                self.assertEqual([r['source_id'] for r in hits],['sample-A'])
                self.assertEqual(len(full_rows(db,[eid])[0]['fields']),2)
        finally:
            with connect() as db, db.cursor() as cur:
                cur.execute("SELECT data_id FROM matsir_source WHERE dataset=%s",(dataset,))
                ids=[r['data_id'] for r in cur.fetchall()]
                for eid in ids:
                    for table in ('matsir_field','value_table','matsir_source','entity_table'):
                        cur.execute(f'DELETE FROM {table} WHERE data_id=%s',(eid,))
                db.commit()
