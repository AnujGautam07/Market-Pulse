import psycopg2
from app.db import get_db_connection
from app.rag import generate_embedding

def embed_all_news():
    print("Connecting to database...")
    conn = get_db_connection()
    cur = conn.cursor()

    print("Fetching articles without embeddings...")
    cur.execute("SELECT article_id, title, content FROM news_articles WHERE embedding IS NULL")
    articles = cur.fetchall()

    if not articles:
        print("No articles need embeddings. You're good to go!")
        return

    print(f"Generating embeddings for {len(articles)} articles. This may take a moment...")
    
    for i, (article_id, title, content) in enumerate(articles):
        # We use title + content for a better embedding, handling missing fields safely
        text_to_embed = f"{title}. {content}"
        embedding = generate_embedding(text_to_embed)
        
        # Format for pgvector
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        
        cur.execute(
            "UPDATE news_articles SET embedding = %s WHERE article_id = %s",
            (embedding_str, article_id)
        )
        
        if (i + 1) % 50 == 0:
            print(f"Processed {i + 1}/{len(articles)} articles...")
            conn.commit()
            
    conn.commit()
    cur.close()
    conn.close()
    print("Successfully populated all embeddings!")

if __name__ == "__main__":
    embed_all_news()
