import psycopg2
import socket

project_ref = 'glkjhxrxkckwbtpmjvzl'

# Try the password with different encodings
# Raw password: _=B=5k%fPH23h=q
# The % could be a literal % sign
password_variants = [
    '_=B=5k%fPH23h=q',          # raw as given
    '_=B=5k%%fPH23h=q',         # escaped %
    '_=B=5k%25fPH23h=q',        # URL decoded (% -> %25)
]

# Try ap-southeast-1 which is most likely for Singapore IPv6
regions = ['ap-southeast-1', 'us-east-1', 'eu-west-1']

print('Testing password variants...')
print()

for pw in password_variants:
    print(f'Password: {repr(pw)}')
    for region in regions:
        host = f'aws-0-{region}.pooler.supabase.com'
        try:
            conn = psycopg2.connect(
                host=host,
                port=5432,
                dbname='postgres',
                user=f'postgres.{project_ref}',
                password=pw,
                sslmode='require',
                connect_timeout=8
            )
            cursor = conn.cursor()
            cursor.execute('SELECT version();')
            v = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            print(f'  CONNECTED via {region}! PG: {v[:50]}')
            print()
            print(f'Working password: {repr(pw)}')
            print(f'DATABASE_URL=postgresql://postgres.{project_ref}:{pw}@{host}:5432/postgres?sslmode=require')
            import sys; sys.exit(0)
        except psycopg2.OperationalError as e:
            err = str(e).replace('\n', ' ')
            if 'not found' in err:
                print(f'  {region}: tenant not found (wrong region or bad pw)')
            elif 'password' in err.lower() or 'auth' in err.lower():
                print(f'  {region}: AUTH FAILED')
            else:
                print(f'  {region}: {err[:80]}')
    print()

print()
print('None worked. Please check the password in Supabase Dashboard:')
print('Project Settings > Database > Database password')
print('Then reset it to something simple (no special chars) for testing.')
