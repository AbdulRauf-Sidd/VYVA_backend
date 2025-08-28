#!/bin/bash

# Define the base URL
URL="http://localhost:8000/api/v1/brain-coach/create-question"

# Define an array of JSON payloads for each row
JSON_PAYLOADS=(
    '{
        "tier": 1,
        "session": 1,
        "question_type": "Memory",
        "question": "Please remember these words: [‘apple, dog, book’]. I’ll ask you again later.",
        "expected_answer": "spoken word",
        "scoring_logic": "+1 per correct answer",
        "theme": "Objects"
    }'
    '{
        "tier": 1,
        "session": 1,
        "question_type": "Attention",
        "question": "Count backwards from 89 to 79.",
        "expected_answer": "spoken word",
        "scoring_logic": "+1 per correct answer",
        "theme": "Sequences"
    }'
    '{
        "tier": 1,
        "session": 1,
        "question_type": "Language",
        "question": "What do ‘dog’ and ‘cat’ have in common?",
        "expected_answer": "spoken word",
        "scoring_logic": "+1 per correct answer",
        "theme": "Word Associations"
    }'
    '{
        "tier": 1,
        "session": 1,
        "question_type": "Orientation",
        "question": "What day of the week was it two days ago?",
        "expected_answer": "spoken word",
        "scoring_logic": "+1 per correct answer",
        "theme": "Place"
    }'
    '{
        "tier": 1,
        "session": 1,
        "question_type": "Reasoning",
        "question": "If you have 15 euros and spend 7, how much do you have left?",
        "expected_answer": "8",
        "scoring_logic": "+1 per correct answer",
        "theme": "Scenarios"
    }'
    '{
        "tier": 1,
        "session": 1,
        "question_type": "Fluency",
        "question": "Name three animals that live in cold climates.",
        "expected_answer": "spoken word",
        "scoring_logic": "+1 per correct answer",
        "theme": "Hobbies"
    }'
)

# Loop through each JSON payload and make the POST request
for payload in "${JSON_PAYLOADS[@]}"; do
    curl -X POST "$URL" \
         -H "Content-Type: application/json" \
         -d "$payload"
    echo "" # Add a newline for readability
done
