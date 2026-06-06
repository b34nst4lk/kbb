"""All prompt templates and JSON schemas for LLM interactions.

Keeping prompts in one place makes them easy to review and iterate on.
JSON schemas are used by Ollama's guided decoding to force valid output.
"""

# --- JSON Schemas for guided decoding ---

PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "education": {"type": "array", "items": {"type": "string"}},
        "work_experience": {"type": "array", "items": {"type": "string"}},
        "life_experience": {"type": "array", "items": {"type": "string"}},
        "interests": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["name", "education", "work_experience", "life_experience", "interests"],
}

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "topic": {
            "type": "string",
            "enum": [
                "education",
                "work_experience",
                "life_experience",
                "skill",
                "opinion",
                "decision",
                "process",
                "general",
            ],
        },
        "rationale": {"type": "string"},
    },
    "required": ["text", "topic", "rationale"],
}

# --- Prompt templates ---

UNDERSTAND_PROFILE_SYSTEM = """You are a precise JSON generator. Given a user's freeform \
self-description, extract structured information. Respond ONLY with a valid JSON object \
matching this schema: {"name": string, "education": [string], "work_experience": [string], \
"life_experience": [string], "interests": [string]}. Do not include conversational text, \
markdown formatting, or anything outside the JSON object. Only include information \
explicitly stated by the user. Do not infer or add anything."""

UNDERSTAND_PROFILE_PROMPT = """Here is the user's profile:
---
{profile_text}
---
Extract the structured information as described. Return only the JSON object."""

GENERATE_QUESTION_SYSTEM = """You are a precise JSON generator and knowledge extraction \
coach. Your job is to ask ONE question that will reveal knowledge the user has, based on \
their background but NOT already documented in their knowledge base.

Guidelines:
- The question should draw on the user's specific expertise or experience
- It should NOT ask something already covered in their knowledge entries
- It should be answerable in 2-5 minutes of thinking/writing
- It should encourage sharing specific, concrete knowledge rather than vague opinions
- Avoid repeating recent questions
- Choose a topic that best fits the question from: education, work_experience, \
life_experience, skill, opinion, decision, process, general

Respond ONLY with a valid JSON object matching this schema: \
{{"text": string, "topic": string, "rationale": string}}. Do not include \
conversational text, markdown formatting, or anything outside the JSON object."""

GENERATE_QUESTION_PROMPT = """## User Profile
{profile_summary}

## Existing Knowledge Topics
{knowledge_topics}

## Recent Questions (avoid repeating these)
{recent_questions}

Generate a question that would extract new knowledge from this user. Return only the \
JSON object."""

RECORD_RESPONSE_SYSTEM = """You are a knowledge recorder. Your job is to take a \
user's response to a question and turn it into a clean, well-structured knowledge \
entry.

CRITICAL RULES:
- Add NO information that was not in the user's response
- Do not elaborate, expand, or add examples the user didn't mention
- Do not add facts, definitions, or context the user didn't provide
- You MAY reorganize for clarity, fix grammar, and add markdown formatting
- You MAY remove filler, hedging, and repetition
- The result should read as a reference document, not a conversation
- Preserve all substantive content the user provided
- Use the user's context (profile) only to understand terminology — never add \
information from it to the recorded entry"""

RECORD_RESPONSE_PROMPT = """## Question Asked
{question}

## User's Response
{response}

## User Context (for terminology only — do not add this information)
{profile_summary}

Transform this response into a clean knowledge entry. Remember: add NOTHING \
that wasn't in the response itself. Return the entry as markdown."""

GENERATE_SLUG_SYSTEM = """You generate short, descriptive file slugs from questions \
and responses. Return ONLY a lowercase hyphenated slug, 3-5 words, no special \
characters, no quotes, no explanation. Examples: "skill-testing-approach", \
"education-phd-experience", "work-architecture-decisions"."""

GENERATE_SLUG_PROMPT = """## Question
{question}

## Response summary
{response}

Generate a short descriptive slug for this log entry. Return ONLY the slug."""
