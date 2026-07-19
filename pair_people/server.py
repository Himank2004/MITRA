from flask import Flask, request, jsonify
import os
import json
from group_matcher import load_user_embeddings, generate_group_suggestions, recommend_groups_for_user

app = Flask(__name__)

# Cache for user embeddings
embeddings_cache = None
last_cache_update = 0
CACHE_TTL = 300  # 5 minutes in seconds

def get_user_embeddings():
    """Get user embeddings with caching"""
    global embeddings_cache, last_cache_update
    
    current_time = int(os.path.getmtime("../User_Embeddings")) if os.path.exists("../User_Embeddings") else 0
    
    # Check if cache is stale
    if embeddings_cache is None or current_time > last_cache_update:
        print("Refreshing embeddings cache...")
        embeddings_cache = load_user_embeddings()
        last_cache_update = current_time
        print(f"Loaded {len(embeddings_cache)} user embeddings")
    
    return embeddings_cache

@app.route('/')
def home():
    return {
        "name": "MITRA Group Matching API",
        "description": "API for recommending similar interest groups",
        "endpoints": [
            "/api/groups/all - Get group suggestions for all users",
            "/api/groups/user/<user_id> - Get group suggestions for a specific user",
            "/api/groups/fixed - Create fixed groups where each user is in exactly one group"
        ]
    }

@app.route('/api/groups/all')
def all_groups():
    """Generate group suggestions for all users"""
    group_size = int(request.args.get('group_size', 4))
    num_suggestions = int(request.args.get('suggestions', 3))
    
    try:
        user_embeddings = get_user_embeddings()
        suggestions = generate_group_suggestions(
            user_embeddings,
            group_size=group_size,
            num_suggestions=num_suggestions
        )
        
        return jsonify({
            "success": True,
            "user_count": len(user_embeddings),
            "group_size": group_size,
            "suggestions_per_user": num_suggestions,
            "groups": suggestions
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/groups/user/<user_id>')
def user_groups(user_id):
    """Generate group suggestions for a specific user"""
    group_size = int(request.args.get('group_size', 4))
    num_suggestions = int(request.args.get('suggestions', 3))
    
    try:
        user_embeddings = get_user_embeddings()
        
        if user_id not in user_embeddings:
            return jsonify({
                "success": False,
                "error": f"User {user_id} not found in embeddings database"
            }), 404
        
        suggestions = generate_group_suggestions(
            user_embeddings,
            group_size=group_size,
            num_suggestions=num_suggestions
        )
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "group_size": group_size,
            "suggestions": suggestions.get(user_id, [])
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/groups/fixed')
def fixed_groups():
    """Create fixed groups where each user is in exactly one group"""
    from group_matcher import create_fixed_groups
    
    group_size = int(request.args.get('group_size', 4))
    
    try:
        user_embeddings = get_user_embeddings()
        groups = create_fixed_groups(user_embeddings, group_size=group_size)
        
        return jsonify({
            "success": True,
            "user_count": len(user_embeddings),
            "group_size": group_size,
            "group_count": len(groups),
            "groups": groups
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug) 