import numpy as np
import random
from typing import Dict, List, Tuple, Any, Set

def load_user_embeddings(path: str = "../User_Embeddings") -> Dict[str, List[float]]:
    """
    Placeholder function to load user embeddings from Chroma DB.
    In a real implementation, this would load from your actual embedding storage.
    
    Returns:
        Dictionary mapping user IDs to their embedding vectors
    """
    # Mock implementation - replace with your actual loading code
    try:
        # Import here to avoid issues if the dependencies aren't installed
        from langchain_community.vectorstores import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings
        
        model_name = "sentence-transformers/all-mpnet-base-v2"
        embeddings = HuggingFaceEmbeddings(
            model_name=model_name, model_kwargs={"device": "cpu"}
        )
        
        # Initialize the Chroma DB
        vectordb = Chroma(
            collection_name="interests",
            persist_directory=path,
            embedding_function=embeddings,
        )
        
        # Get the internal collection object
        collection = vectordb._collection
        
        # Get all embeddings and metadata
        results = collection.get(include=["embeddings", "metadatas"])
        
        # Convert into a user-friendly structure
        user_id_to_embedding = {}
        for embedding, meta in zip(results["embeddings"], results["metadatas"]):
            user_id = meta.get("user_id")
            if user_id is not None:
                user_id_to_embedding[user_id] = embedding
                
        return user_id_to_embedding
        
    except Exception as e:
        print(f"Error loading embeddings: {e}")
        # Return mock data for testing if loading fails
        return {
            f"user_{i}": np.random.rand(384).tolist() 
            for i in range(20)
        }

def compute_similarity_matrix(user_embeddings: Dict[str, List[float]]) -> Tuple[List[str], np.ndarray]:
    """
    Compute similarity matrix between all users.
    
    Args:
        user_embeddings: Dictionary mapping user IDs to their embedding vectors
        
    Returns:
        Tuple of (user_ids, similarity_matrix)
    """
    user_ids = list(user_embeddings.keys())
    embeddings = np.array([user_embeddings[uid] for uid in user_ids])
    
    # Normalize embeddings for cosine similarity
    normalized_embeddings = embeddings / np.linalg.norm(embeddings, axis=1)[:, np.newaxis]
    
    # Compute cosine similarity matrix
    similarity_matrix = np.dot(normalized_embeddings, normalized_embeddings.T)
    
    return user_ids, similarity_matrix

def generate_group_suggestions(
    user_embeddings: Dict[str, List[float]], 
    group_size: int = 4,
    num_suggestions: int = 3,
    overlap_allowed: bool = True
) -> Dict[str, List[List[str]]]:
    """
    Generate multiple group suggestions for each user.
    
    Args:
        user_embeddings: Dictionary mapping user IDs to their embedding vectors
        group_size: Size of each group
        num_suggestions: Number of different group suggestions to generate per user
        overlap_allowed: Whether different suggestions can contain overlapping members
        
    Returns:
        Dictionary mapping user IDs to lists of group suggestions
    """
    if len(user_embeddings) < group_size:
        return {uid: [[uid]] for uid in user_embeddings}
    
    # Compute similarity matrix
    user_ids, similarity_matrix = compute_similarity_matrix(user_embeddings)
    
    # Store group suggestions for each user
    user_suggestions = {}
    
    for i, user_id in enumerate(user_ids):
        # Get similarities to all other users
        similarities = [(j, similarity_matrix[i, j]) for j in range(len(user_ids)) if j != i]
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        user_suggestions[user_id] = []
        
        # For each suggestion
        for suggestion_idx in range(num_suggestions):
            if suggestion_idx == 0:
                # First suggestion: most similar users
                top_users_idx = [idx for idx, _ in similarities[:(group_size-1)]]
                group = [user_id] + [user_ids[idx] for idx in top_users_idx]
                user_suggestions[user_id].append(group)
            
            elif suggestion_idx == 1 and len(user_ids) >= group_size * 2:
                # Second suggestion: mix of similar and diverse users
                half_size = (group_size - 1) // 2
                remainder = (group_size - 1) - half_size
                
                # Take some similar users
                similar_users_idx = [idx for idx, _ in similarities[:half_size]]
                
                # Take some diverse users (from the middle of the list)
                middle_start = len(similarities) // 2 - remainder // 2
                diverse_users_idx = [idx for idx, _ in similarities[middle_start:middle_start+remainder]]
                
                group = [user_id] + [user_ids[idx] for idx in similar_users_idx + diverse_users_idx]
                user_suggestions[user_id].append(group)
            
            else:
                # Additional suggestions with randomization
                used_users = set()
                if not overlap_allowed:
                    for prev_group in user_suggestions[user_id]:
                        for uid in prev_group:
                            if uid != user_id:  # Don't exclude the current user
                                used_users.add(uid)
                
                available_users = [
                    (idx, sim) for idx, sim in similarities 
                    if user_ids[idx] not in used_users
                ]
                
                if len(available_users) >= group_size - 1:
                    # Mix of similarity and randomness
                    # Take some top users by similarity
                    top_count = max(1, (group_size - 1) // 2)
                    top_users = [idx for idx, _ in available_users[:top_count]]
                    
                    # Take some random users from the rest
                    remaining = [idx for idx, _ in available_users[top_count:]]
                    random_count = min(len(remaining), group_size - 1 - top_count)
                    random_users = random.sample(remaining, random_count)
                    
                    group = [user_id] + [user_ids[idx] for idx in top_users + random_users]
                    user_suggestions[user_id].append(group)
                elif len(available_users) > 0:
                    # Not enough users for a full group, use what we have
                    group = [user_id] + [user_ids[idx] for idx, _ in available_users]
                    user_suggestions[user_id].append(group)
                else:
                    # No more users available, reuse some users from other groups
                    # with preference for less used users
                    user_usage_count = {}
                    for prev_group in user_suggestions[user_id]:
                        for uid in prev_group:
                            if uid != user_id:
                                user_usage_count[uid] = user_usage_count.get(uid, 0) + 1
                    
                    # Sort users by usage count
                    sorted_users = sorted(
                        [(uid, user_usage_count.get(uid, 0)) for uid in user_ids if uid != user_id],
                        key=lambda x: x[1]
                    )
                    
                    # Take the least used users
                    least_used = [uid for uid, _ in sorted_users[:(group_size-1)]]
                    group = [user_id] + least_used
                    user_suggestions[user_id].append(group)
    
    return user_suggestions

def create_fixed_groups(
    user_embeddings: Dict[str, List[float]], 
    group_size: int = 4
) -> List[List[str]]:
    """
    Create fixed groups of users based on similarity.
    This puts each user in exactly one group.
    
    Args:
        user_embeddings: Dictionary mapping user IDs to their embedding vectors
        group_size: Size of each group
        
    Returns:
        List of groups, where each group is a list of user IDs
    """
    user_ids, similarity_matrix = compute_similarity_matrix(user_embeddings)
    
    # Create a copy of user_ids to work with
    remaining_users = user_ids.copy()
    groups = []
    
    while len(remaining_users) >= group_size:
        # Pick a random user to start the group
        anchor_user = remaining_users[0]
        anchor_idx = user_ids.index(anchor_user)
        
        # Find the most similar users to the anchor
        similarities = []
        for user in remaining_users[1:]:
            user_idx = user_ids.index(user)
            similarities.append((user, similarity_matrix[anchor_idx, user_idx]))
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Create a group with the anchor and the most similar users
        group = [anchor_user] + [user for user, _ in similarities[:(group_size-1)]]
        groups.append(group)
        
        # Remove grouped users from remaining_users
        for user in group:
            remaining_users.remove(user)
    
    # Handle leftover users by adding them to existing groups
    if remaining_users:
        for i, user in enumerate(remaining_users):
            groups[i % len(groups)].append(user)
    
    return groups

def recommend_groups_for_user(user_id: str, user_embeddings: Dict[str, List[float]], group_size: int = 4) -> List[List[str]]:
    """
    Recommend multiple groups for a specific user.
    
    Args:
        user_id: The ID of the user to recommend groups for
        user_embeddings: Dictionary mapping user IDs to their embedding vectors
        group_size: Size of each group
        
    Returns:
        List of recommended groups (each group is a list of user IDs)
    """
    if user_id not in user_embeddings:
        return []
    
    suggestions = generate_group_suggestions(
        user_embeddings, 
        group_size=group_size,
        num_suggestions=3
    )
    
    return suggestions.get(user_id, [])

if __name__ == "__main__":
    # Example usage
    user_embeddings = load_user_embeddings()
    print(f"Loaded {len(user_embeddings)} user embeddings.")
    
    # Generate group suggestions for all users
    suggestions = generate_group_suggestions(user_embeddings, group_size=4, num_suggestions=3)
    
    # Print first 5 users' suggestions
    count = 0
    for user_id, groups in suggestions.items():
        if count >= 5:
            break
            
        print(f"\nSuggested groups for user {user_id}:")
        for i, group in enumerate(groups, 1):
            print(f"  Suggestion {i}: {group}")
        
        count += 1
    
    # Create fixed groups (each user in exactly one group)
    fixed_groups = create_fixed_groups(user_embeddings, group_size=4)
    print(f"\nCreated {len(fixed_groups)} fixed groups:")
    for i, group in enumerate(fixed_groups, 1):
        print(f"  Group {i}: {group}") 