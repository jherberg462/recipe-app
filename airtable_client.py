# airtable_client.py
import os
from pyairtable import Api

# --- Configuration ---
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

# print(f"--- DEBUG: Loading Token: {AIRTABLE_TOKEN}")
# print(f"--- DEBUG: Loading Base ID: {AIRTABLE_BASE_ID}")

if not AIRTABLE_TOKEN or not AIRTABLE_BASE_ID:
    raise EnvironmentError("AIRTABLE_TOKEN and AIRTABLE_BASE_ID must be set as environment variables.")

# Initialize the API
api = Api(AIRTABLE_TOKEN)


table_users = api.table(AIRTABLE_BASE_ID, "Users")
table_reviewers = api.table(AIRTABLE_BASE_ID, "Reviewers")
table_ingredients = api.table(AIRTABLE_BASE_ID, "Ingredients")
table_recipes = api.table(AIRTABLE_BASE_ID, "Recipes")

# --- Helper Functions ---

def _process_record(record):
    """Converts an Airtable record into a simple dictionary."""
    if not record:
        return None
    return {"id": record["id"], **record["fields"]}

def _process_records(records):
    """Converts a list of Airtable records into a list of dictionaries."""
    return [_process_record(record) for record in records]

# --- User Functions ---

def create_user(first_name, last_name, email):
    """Creates a new user record."""
    try:
        new_user = {
            "FirstName": first_name,
            "LastName": last_name,
            "email": email,
            "numApproved": 0,
            "numRejected": 0
        }
        record = table_users.create(new_user)
        return _process_record(record)
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def find_user_by_email(email):
    """Finds a user by their email address."""
    formula = f"{{email}} = '{email}'"
    records = table_users.all(formula=formula)
    if records:
        return _process_record(records[0])
    return None

def get_user_by_id(record_id):
    """Gets a user by their Airtable Record ID."""
    try:
        return _process_record(table_users.get(record_id))
    except Exception:
        return None

def update_user_stats(user_id, stat_to_increment):
    """Increments numApproved or numRejected for a user."""
    user = get_user_by_id(user_id)
    if not user:
        return False
    
    current_count = user.get(stat_to_increment, 0)
    new_count = current_count + 1
    
    table_users.update(user_id, {stat_to_increment: new_count})
    return True

# --- Reviewer Functions ---

def create_reviewer(first_name, last_name, email):
    """Creates a new reviewer record."""
    try:
        new_reviewer = {
            "FirstName": first_name,
            "LastName": last_name,
            "email": email
        }
        record = table_reviewers.create(new_reviewer)
        return _process_record(record)
    except Exception as e:
        print(f"Error creating reviewer: {e}")
        return None

def find_reviewer_by_email(email):
    """Finds a reviewer by their email address."""
    formula = f"{{email}} = '{email}'"
    records = table_reviewers.all(formula=formula)
    if records:
        return _process_record(records[0])
    return None

def get_reviewer_by_id(record_id):
    """Gets a reviewer by their Airtable Record ID."""
    try:
        return _process_record(table_reviewers.get(record_id))
    except Exception:
        return None

# --- Ingredient Functions ---

def add_ingredient(ingredient_name):
    """Adds a new ingredient to the Ingredients table."""
    try:
        record = table_ingredients.create({"Ingredient": ingredient_name})
        return _process_record(record)
    except Exception as e:
        print(f"Error adding ingredient: {e}")
        return None

def get_all_ingredients():
    """Fetches all ingredients, sorted by name."""
    records = table_ingredients.all(sort=["Ingredient"])
    return _process_records(records)

# --- Recipe Functions ---

def create_recipe(user_id, price, is_vegan, ingredient_ids):
    """Creates a new recipe and links it to ingredients."""
    try:
        price_float = float(price)
        price_2x = price_float * 2
        price_3x = price_float * 3

        new_recipe = {
            "userID": [user_id],
            "status": "unassigned",
            "price": price_float,
            "price_2x": price_2x,
            "price_3x": price_3x,
            "is_vegan": is_vegan,
            "ingredients": ingredient_ids
        }
        
        record = table_recipes.create(new_recipe)
        return _process_record(record)
    except Exception as e:
        print(f"Error creating recipe: {e}")
        return None

def get_recipe_by_id(recipe_id):
    """Fetches a single recipe by its Record ID."""
    try:
        return _process_record(table_recipes.get(recipe_id))
    except Exception:
        return None

def get_unassigned_recipes():
    """Fetches all recipes with 'unassigned' status."""
    formula = "{status} = 'unassigned'"
    records = table_recipes.all(formula=formula)
    return _process_records(records)

def get_recipes_by_reviewer(reviewer_id, status):
    """Finds recipes assigned to a specific reviewer with a specific status."""
    formula = f"{{status}} = '{status}'"
    all_records_with_status = table_recipes.all(formula=formula)
    matching_recipes = []
    for record in all_records_with_status:
        linked_reviewer_ids = record['fields'].get('reviewerID', [])
        if reviewer_id in linked_reviewer_ids:
            matching_recipes.append(record)
    return _process_records(matching_recipes)


def get_recipes_by_user(user_id, status):
    """Finds recipes for a specific user with a specific status."""

    formula = f"{{status}} = '{status}'"
    all_records_with_status = table_recipes.all(formula=formula)
    matching_recipes = []
    for record in all_records_with_status:
        linked_user_ids = record['fields'].get('userID', [])
        if user_id in linked_user_ids:
            matching_recipes.append(record)
    return _process_records(matching_recipes)

def assign_recipe_to_reviewer(recipe_id, reviewer_id):
    """Updates a recipe's status to 'inProgress' and links the reviewer."""
    fields = {
        "status": "inProgress",
        "reviewerID": [reviewer_id]
    }
    table_recipes.update(recipe_id, fields)

def update_recipe_status(recipe_id, new_status, user_id_for_stats=None):
    """Updates a recipe's status (e.g., 'approved', 'rejected')."""
    fields = {"status": new_status}
    
    # If approving or rejecting, update the user's stats
    if new_status == "approved" and user_id_for_stats:
        update_user_stats(user_id_for_stats, "numApproved")
    elif new_status == "rejected" and user_id_for_stats:
        update_user_stats(user_id_for_stats, "numRejected")
    table_recipes.update(recipe_id, fields)

def update_rejected_recipe(recipe_id, is_vegan, ingredient_ids):
    """Updates a modified rejected recipe and sets it to 'unassigned'."""
    fields = {
        "is_vegan": is_vegan,
        "ingredients": ingredient_ids,
        "status": "unassigned",
        "reviewerID": []
    }
    table_recipes.update(recipe_id, fields)