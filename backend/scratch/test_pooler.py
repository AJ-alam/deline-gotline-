import psycopg2

host = 'aws-1-ap-northeast-1.pooler.supabase.com'
project_ref = 'glkjhxrxkckwbtpmjvzl'
password = 'DggPass2024!'

print('=' * 60)
print('Testing Supabase Session Pooler')
print('=' * 60)
print(f'Host:     {host}')
print(f'User:     postgres.{project_ref}')
print()

try:
    conn = psycopg2.connect(
        host=host, port=5432, dbname='postgres',
        user=f'postgres.{project_ref}',
        password=password,
        sslmode='require', connect_timeout=15
    )
    cursor = conn.cursor()

    cursor.execute('SELECT version();')
    print(f'PostgreSQL: {cursor.fetchone()[0][:70]}')

    cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name;"
    )
    tables = cursor.fetchall()
    print(f'Tables: {len(tables)} ({"empty - ready for migrations" if not tables else ", ".join(t[0] for t in tables[:5])})')

    cursor.close()
    conn.close()

    print()
    print('=' * 60)
    print('SUCCESS! DB IS CONNECTED AND WORKING!')
    print('=' * 60)

except Exception as e:
    print(f'FAILED: {e}')
