"""Script to check markets table for duplicate names."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def check_markets():
    """Check markets in the database."""
    try:
        # Create engine with correct connection string
        engine = create_engine('postgresql://postgres:12345678@localhost:5432/deals')
        Session = sessionmaker(bind=engine)
        session = Session()

        # Execute query
        result = session.execute(
            text("SELECT id, name, type FROM markets ORDER BY name")
        )

        # Print results
        print("\nMarkets in database:")
        print("-------------------")
        for row in result:
            print(f"ID: {row[0]}, Name: {row[1]}, Type: {row[2]}")

        session.close()
    except Exception as e:
        print(f"Database transaction failed: {e}")

if __name__ == "__main__":
    check_markets() 