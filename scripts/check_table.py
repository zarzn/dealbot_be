from sqlalchemy import create_engine, text

# Create engine
engine = create_engine('postgresql://postgres:12345678@localhost:5432/deals')

# Query to check table structure
query = text('''
    SELECT column_name, data_type, is_nullable 
    FROM information_schema.columns 
    WHERE table_name = 'users' 
    ORDER BY ordinal_position;
''')

# Execute query
with engine.connect() as conn:
    result = conn.execute(query)
    print("\nUsers table structure:")
    print("Column Name | Data Type | Nullable")
    print("-" * 50)
    for row in result:
        print(f"{row[0]:<20} | {row[1]:<15} | {row[2]}") 