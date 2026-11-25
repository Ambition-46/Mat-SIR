"""Register a property's unit, converting existing values from an explicit known unit."""
import argparse
from .service import connect
from .units import convert, unit_name


def configure(db, name, target, stored_unit=None):
    convert(1, target, target)  # Validate the unit before changing metadata.
    try:
        with db.cursor() as cur:
            cur.execute('SELECT property_id FROM property_table WHERE property_name=%s FOR UPDATE',(name,))
            prop=cur.fetchone()
            if not prop: raise ValueError('Unknown standard property')
            cur.execute('SELECT standard_unit FROM matsir_property_unit WHERE property_name=%s',(name,))
            old=cur.fetchone()
            if old:
                if unit_name(old['standard_unit'])==unit_name(target): return
                raise ValueError('Standard unit already registered; do not change a published property scale')
            cur.execute('SELECT value FROM value_table WHERE property_id=%s FOR UPDATE',(prop['property_id'],))
            values=[r['value'] for r in cur.fetchall()]
            if values and not stored_unit: raise ValueError('Existing values require an explicit --stored-unit')
            # Convert distinct lexical values in one CASE statement to avoid cascading replacements.
            pairs=[(v,str(convert(v,stored_unit,target))) for v in dict.fromkeys(values)]
            if pairs:
                sql='UPDATE value_table SET value=CASE value '+ ' '.join('WHEN %s THEN %s' for _ in pairs)+' ELSE value END WHERE property_id=%s'
                cur.execute(sql,tuple(x for pair in pairs for x in pair)+(prop['property_id'],))
            cur.execute('INSERT INTO matsir_property_unit(property_name,standard_unit) VALUES (%s,%s)',(name,target))
        db.commit()
    except Exception:
        db.rollback()
        raise

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('property');cli.add_argument('unit');cli.add_argument('--stored-unit')
    args=cli.parse_args()
    with connect() as db: configure(db,args.property,args.unit,args.stored_unit)
