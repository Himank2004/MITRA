# User Interest Group Matcher

A server-based solution for matching users into groups based on their interest similarities.

## Features

- **Multiple Group Suggestions** - Generates multiple possible groups for each user
- **Flexible Group Sizes** - Support for any group size (pairs, triplets, quads, etc.)
- **Server-Based API** - Simple Flask server for easy integration with your application
- **Different Grouping Strategies**:
  - First suggestion: Most similar users based on interests
  - Second suggestion: Mix of similar and diverse users
  - Third suggestion: Introduces some randomness for variety

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Make sure your user embeddings are in the correct location (`../User_Embeddings` by default)

3. Start the server:
   ```
   python server.py
   ```

## API Endpoints

### Get Group Suggestions for All Users
```
GET /api/groups/all?group_size=4&suggestions=3
```
Parameters:
- `group_size` - Number of users per group (default: 4)
- `suggestions` - Number of different suggestions per user (default: 3)

### Get Group Suggestions for a Specific User
```
GET /api/groups/user/123?group_size=4&suggestions=3
```
Parameters:
- `group_size` - Number of users per group (default: 4)
- `suggestions` - Number of different suggestions per user (default: 3)

### Create Fixed Groups (Each User in One Group)
```
GET /api/groups/fixed?group_size=4
```
Parameters:
- `group_size` - Number of users per group (default: 4)

## Usage Examples

### Using the API from JavaScript

```javascript
// Get group suggestions for a specific user
fetch('/api/groups/user/123?group_size=4&suggestions=3')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('Groups for user:', data.suggestions);
    } else {
      console.error('Error:', data.error);
    }
  });
```

### Using the Module Directly in Python

```python
from group_matcher import load_user_embeddings, generate_group_suggestions

# Load user embeddings
user_embeddings = load_user_embeddings()

# Generate group suggestions for all users
suggestions = generate_group_suggestions(
    user_embeddings,
    group_size=4,
    num_suggestions=3
)

# Get groups for a specific user
user_id = "123"
user_groups = suggestions.get(user_id, [])
print(f"Groups for user {user_id}:", user_groups)
```

## How It Works

1. User interests are stored in a database as arrays (e.g., `['Cooking', 'Art']`)
2. These interests are converted to embeddings and stored in a Chroma database
3. When group suggestions are requested, the system:
   - Computes similarity scores between all users
   - For each user, generates multiple possible groups
   - Each group suggestion uses a different strategy to ensure variety
4. The grouping strategies ensure a good balance of similarity and diversity

## Customization

You can modify `group_matcher.py` to change:
- The number of suggestions per user
- Group size defaults
- Grouping strategies
- Handling of edge cases 