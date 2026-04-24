import socket
import psycopg2

host = 'db.glkjhxrxkckwbtpmjvzl.supabase.co'
password = '_=B=5k%fPH23h=q'

print('=== DNS Check ===')
try:
    ip = socket.gethostbyname(host)
    print(f'IPv4 resolved: {ip}')
    ipv4_ok = True
except Exception as e:
    print(f'IPv4 DNS failed: {e}')
    ipv4_ok = False

try:
    results = socket.getaddrinfo(host, 5432)
    for r in results:
        print(f'  Address found: {r[0].name} -> {r[4]}')
except Exception as e2:
    print(f'All DNS failed: {e2}')

print()
print('=== Direct Connection Test (port 5432) ===')
try:
    conn = psycopg2.connect(
        host=host,
        port=5432,
        dbname='postgres',
        user='postgres',
        password=password,
        sslmode='require',
        connect_timeout=15
    )
    cursor = conn.cursor()
    cursor.execute('SELECT version();')
    version = cursor.fetchone()[0]
    print(f'SUCCESS! PostgreSQL: {version[:70]}')
    cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name;"
    )
    tables = cursor.fetchall()
    print(f'Tables in DB: {len(tables)}')
    for t in tables[:10]:
        print(f'  - {t[0]}')
    cursor.close()
    conn.close()
    print()
    print('DB CONNECTION IS WORKING!')
except Exception as e:
    print(f'Direct connection failed: {e}')
    print()
    print('=== Trying Session Pooler regions ===')
    project_ref = 'glkjhxrxkckwbtpmjvzl'
    regions = ['ap-southeast-1', 'us-east-1', 'eu-west-1', 'ca-central-1']
    for region in regions:
        pooler_host = f'aws-0-{region}.pooler.supabase.com'
        print(f'Trying {pooler_host}...')
        try:
            conn2 = psycopg2.connect(
                host=pooler_host,
                port=5432,
                dbname='postgres',
                user=f'postgres.{project_ref}',
                password=password,
                sslmode='require',
                connect_timeout=8
            )
            cursor2 = conn2.cursor()
            cursor2.execute('SELECT version();')
            v = cursor2.fetchone()[0]
            print(f'  SUCCESS via {region}! PG: {v[:50]}')
            cursor2.close()
            conn2.close()
            print()
            print(f'USE THIS IN .env:')
            print(f'DATABASE_URL=postgresql://postgres.{project_ref}:{password}@{pooler_host}:5432/postgres?sslmode=require')
            break
        except psycopg2.OperationalError as e2:
            err = str(e2).replace('\n', ' ')
            if 'not found' in err:
                print(f'  {region}: wrong region')
            elif 'password' in err.lower() or 'authentication' in err.lower():
                print(f'  {region}: AUTH ERROR - {err[:80]}')
            else:
                print(f'  {region}: {err[:80]}')
