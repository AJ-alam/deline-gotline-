import psycopg2
import socket

project_ref = 'glkjhxrxkckwbtpmjvzl'
password = '_=B=5k%fPH23h=q'

# More comprehensive region list - IPv6 2406:da14 is ap-southeast-1 (Singapore)
# Supabase uses these pooler regions:
all_regions = [
    'ap-southeast-1',   # Singapore
    'ap-southeast-2',   # Sydney  
    'ap-northeast-1',   # Tokyo
    'ap-northeast-2',   # Seoul
    'ap-south-1',       # Mumbai
    'us-east-1',        # N. Virginia
    'us-east-2',        # Ohio
    'us-west-1',        # N. California
    'us-west-2',        # Oregon
    'eu-west-1',        # Ireland
    'eu-west-2',        # London
    'eu-west-3',        # Paris
    'eu-central-1',     # Frankfurt
    'eu-north-1',       # Stockholm
    'ca-central-1',     # Canada
    'sa-east-1',        # Sao Paulo
]

print(f'Project: {project_ref}')
print(f'Password: {password}')
print()

for region in all_regions:
    host = f'aws-0-{region}.pooler.supabase.com'
    # First check if hostname resolves
    try:
        ip = socket.gethostbyname(host)
        dns_ok = True
    except:
        dns_ok = False
        print(f'{region}: DNS failed, skipping')
        continue

    try:
        conn = psycopg2.connect(
            host=host,
            port=5432,
            dbname='postgres',
            user=f'postgres.{project_ref}',
            password=password,
            sslmode='require',
            connect_timeout=8
        )
        cursor = conn.cursor()
        cursor.execute('SELECT version();')
        v = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        print('=' * 60)
        print(f'CONNECTED! Region: {region}')
        print(f'PostgreSQL: {v[:60]}')
        print()
        print('Copy this DATABASE_URL:')
        print(f'DATABASE_URL=postgresql://postgres.{project_ref}:{password}@{host}:5432/postgres?sslmode=require')
        print('=' * 60)
        break

    except psycopg2.OperationalError as e:
        err = str(e).replace('\n', ' ')
        if 'not found' in err or 'ENOTFOUND' in err:
            print(f'{region}: wrong region (tenant not here)')
        elif 'password' in err.lower() or 'authentication' in err.lower():
            print(f'{region}: AUTH FAILED -> {err[:100]}')
        elif 'timeout' in err.lower() or 'timed out' in err.lower():
            print(f'{region}: TIMEOUT')
        else:
            print(f'{region}: {err[:100]}')
    except Exception as e:
        print(f'{region}: ERROR: {str(e)[:80]}')
