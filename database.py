from neo4j import GraphDatabase

# Your exact database details
URI = "neo4j+s://a125825f.databases.neo4j.io"
USERNAME = "a125825f"
PASSWORD = "dPaAFxOKAArthVhVGqqfk9wYj1d7HIVTze8DJCYZR_M" 

def test_connection():
    print("Connecting to AuraDB...")
    try:
        # Create the connection
        driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
        driver.verify_connectivity()
        print("✅ SUCCESS! Your Mac is connected to Neo4j.")
        
        # Write one test piece of data
        query = "CREATE (t:TestNode {message: 'Hello HackHazards!'}) RETURN t"
        with driver.session() as session:
            session.run(query)
            print("✅ SUCCESS! Test node created in the database.")
            
        driver.close()
    except Exception as e:
        print("❌ FAILED TO CONNECT:")
        print(e)

if __name__ == "__main__":
    test_connection()