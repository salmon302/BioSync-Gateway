with open(r'C:\Users\salmo\AppData\Local\Temp\ext.sql', 'w') as f:
    f.write('CREATE EXTENSION IF NOT EXISTS pgcrypto;\n')
    f.write('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";\n')
print("written")
