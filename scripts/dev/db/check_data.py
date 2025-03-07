import asyncio
import asyncpg

async def check_data():
    # Connect to the database
    conn = await asyncpg.connect(
        user='postgres',
        password='12345678',
        database='agentic_deals_test',
        host='localhost',
        port=5432
    )
    
    try:
        # Check users table data
        users = await conn.fetch("SELECT * FROM users")
        print("\nUsers in database:")
        if not users:
            print("No users found")
        else:
            for user in users:
                print(f"\nUser ID: {user['id']}")
                print(f"Email: {user['email']}")
                print(f"Name: {user['name']}")
                print(f"Status: {user['status']}")
                print(f"Token Balance: {user['token_balance']}")
                print(f"Created At: {user['created_at']}")

        # Check markets table data
        markets = await conn.fetch("SELECT * FROM markets")
        print("\nMarkets in database:")
        if not markets:
            print("No markets found")
        else:
            for market in markets:
                print(f"\nMarket ID: {market['id']}")
                print(f"Name: {market['name']}")
                print(f"Type: {market['type']}")
                print(f"Status: {market['status']}")
                print(f"Config: {market['config']}")
                print(f"Is Active: {market['is_active']}")
                print(f"Created At: {market['created_at']}")

        # Check goals table data
        goals = await conn.fetch("SELECT * FROM goals")
        print("\nGoals in database:")
        if not goals:
            print("No goals found")
        else:
            for goal in goals:
                print(f"\nGoal ID: {goal['id']}")
                print(f"User ID: {goal['user_id']}")
                print(f"Title: {goal['title']}")
                print(f"Category: {goal['item_category']}")
                print(f"Constraints: {goal['constraints']}")
                print(f"Status: {goal['status']}")
                print(f"Created At: {goal['created_at']}")

        # Check deals table data
        deals = await conn.fetch("SELECT * FROM deals")
        print("\nDeals in database:")
        if not deals:
            print("No deals found")
        else:
            for deal in deals:
                print(f"\nDeal ID: {deal['id']}")
                print(f"Title: {deal['title']}")
                print(f"Price: {deal['price']}")
                print(f"Original Price: {deal['original_price']}")
                print(f"Source: {deal['source']}")
                print(f"Status: {deal['status']}")
                print(f"Created At: {deal['created_at']}")

        # Check price points table data
        price_points = await conn.fetch("SELECT * FROM price_points")
        print("\nPrice Points in database:")
        if not price_points:
            print("No price points found")
        else:
            for point in price_points:
                print(f"\nPrice Point ID: {point['id']}")
                print(f"Deal ID: {point['deal_id']}")
                print(f"Price: {point['price']}")
                print(f"Source: {point['source']}")
                print(f"Timestamp: {point['timestamp']}")

        # Check notifications table data
        notifications = await conn.fetch("SELECT * FROM notifications")
        print("\nNotifications in database:")
        if not notifications:
            print("No notifications found")
        else:
            for notif in notifications:
                print(f"\nNotification ID: {notif['id']}")
                print(f"Title: {notif['title']}")
                print(f"Message: {notif['message']}")
                print(f"Type: {notif['type']}")
                print(f"Priority: {notif['priority']}")
                print(f"Status: {notif['status']}")
                print(f"Created At: {notif['created_at']}")

        # Check token pricing table data
        token_pricing = await conn.fetch("SELECT * FROM token_pricing")
        print("\nToken Pricing in database:")
        if not token_pricing:
            print("No token pricing found")
        else:
            for pricing in token_pricing:
                print(f"\nService Type: {pricing['service_type']}")
                print(f"Token Cost: {pricing['token_cost']}")
                print(f"Valid From: {pricing['valid_from']}")
                print(f"Is Active: {pricing['is_active']}")
                print(f"Created At: {pricing['created_at']}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_data()) 