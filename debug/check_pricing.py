import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        user='postgres',
        password='12345678',
        database='deals',
        host='localhost'
    )
    
    # Check all token_pricing records
    records = await conn.fetch('SELECT id, service_type, token_cost, valid_from, valid_to, is_active FROM token_pricing')
    print("Available pricing records in token_pricing table:")
    for record in records:
        print(f"ID: {record['id']}, Service Type: {record['service_type']}, Cost: {record['token_cost']}, "
              f"Valid From: {record['valid_from']}, Valid To: {record['valid_to']}, Active: {record['is_active']}")
    
    # Check specifically for market_search
    market_search_records = await conn.fetch("SELECT id, service_type, token_cost, valid_from, valid_to, is_active FROM token_pricing WHERE service_type = 'market_search'")
    print("\nMarket Search pricing records:")
    if market_search_records:
        for record in market_search_records:
            print(f"ID: {record['id']}, Service Type: {record['service_type']}, Cost: {record['token_cost']}, "
                  f"Valid From: {record['valid_from']}, Valid To: {record['valid_to']}, Active: {record['is_active']}")
    else:
        print("No pricing records found for 'market_search'")
    
    # Check for case-insensitive match
    case_insensitive_records = await conn.fetch("SELECT id, service_type, token_cost, valid_from, valid_to, is_active FROM token_pricing WHERE LOWER(service_type) = LOWER('market_search')")
    print("\nCase-insensitive Market Search pricing records:")
    if case_insensitive_records:
        for record in case_insensitive_records:
            print(f"ID: {record['id']}, Service Type: {record['service_type']}, Cost: {record['token_cost']}, "
                  f"Valid From: {record['valid_from']}, Valid To: {record['valid_to']}, Active: {record['is_active']}")
    else:
        print("No case-insensitive pricing records found for 'market_search'")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main()) 