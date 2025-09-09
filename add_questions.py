import httpx
import asyncio
import json
from typing import List, Dict, Any
import time

async def create_question(question_data: Dict[str, Any], api_url: str, headers: Dict[str, str]):
    """
    Send a single question to the API
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                json=question_data,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 201:
                print(f"✓ Successfully created question ID {question_data.get('id', 'N/A')}")
                return response.json()
            else:
                print(f"✗ Failed to create question ID {question_data.get('id', 'N/A')}: {response.status_code} - {response.text}")
                return None
                
    except httpx.RequestError as e:
        print(f"✗ Network error for question ID {question_data.get('id', 'N/A')}: {str(e)}")
        return None
    except Exception as e:
        print(f"✗ Unexpected error for question ID {question_data.get('id', 'N/A')}: {str(e)}")
        return None

async def send_questions_to_api(questions_file: str, api_url: str, auth_token: str = None, batch_size: int = 5, delay: float = 0.5):
    """
    Send all questions from JSON file to the API
    """
    # Load questions from JSON file
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    
    # Prepare headers
    headers = {
        "Content-Type": "application/json"
    }
    
    # Add authorization header if token is provided
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    print(f"Starting to send {len(questions)} questions to API...")
    print(f"API URL: {api_url}")
    print(f"Batch size: {batch_size}")
    print(f"Delay between batches: {delay} seconds")
    print("-" * 50)
    
    successful = 0
    failed = 0
    
    # Process questions in batches to avoid overwhelming the server
    for i in range(0, len(questions), batch_size):
        batch = questions[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(questions)-1)//batch_size + 1} ({len(batch)} questions)")
        
        # Create tasks for current batch
        tasks = []
        for question in batch:
            # Remove ID if it exists in the question data (API might auto-generate IDs)
            question_data = question.copy()
            question_data.pop('id', None)  # Remove ID field
            
            task = create_question(question_data, api_url, headers)
            tasks.append(task)
        
        # Execute batch concurrently
        results = await asyncio.gather(*tasks)
        
        # Count results
        for result in results:
            if result is not None:
                successful += 1
            else:
                failed += 1
        
        # Add delay between batches if not the last batch
        if i + batch_size < len(questions):
            print(f"Waiting {delay} seconds before next batch...")
            await asyncio.sleep(delay)
    
    print("-" * 50)
    print(f"Completed! Successful: {successful}, Failed: {failed}")
    return successful, failed

async def main():
    # Configuration
    QUESTIONS_FILE = "merged_questions.json"  # Your merged JSON file
    API_URL = "http://localhost:8000/api/v1/brain-coach/questions"  # Replace with your actual API URL
    # AUTH_TOKEN = "your-auth-token-here"  # Replace with your actual auth token if needed
    
    # Choose which method to use:
    
    # Option 1: Async with validation (recommended)
    # successful, failed = await send_questions_with_validation(QUESTIONS_FILE, API_URL, AUTH_TOKEN)
    
    # Option 2: Async without validation
    successful, failed = await send_questions_to_api(QUESTIONS_FILE, API_URL, None)
    
    # Option 3: Synchronous (if you prefer)
    # successful, failed = send_questions_sync(QUESTIONS_FILE, API_URL, AUTH_TOKEN)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
