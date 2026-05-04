import psycopg2

passwords = ['admin', 'root', '', 'postgres', 'password', 'Safouaine', 'safouaine']

print("Testing common passwords...")
for p in passwords:
    try:
        psycopg2.connect(host='localhost', port=5432, user='postgres', password=p, dbname='datacenter-dw')
        print(f"✅ SUCCESS! Password is: '{p}'")
        break
    except Exception as e:
        print(f"Failed with password: '{p}'")
