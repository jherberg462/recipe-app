# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import airtable_client as db 

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_fallback_secret_key_if_not_set')

# --- Helper Functions ---

def get_user_session():
    """Returns the user/reviewer dict from session if it exists."""
    return session.get('user', None)

def get_user_role():
    """Returns the role ('user' or 'reviewer') from session."""
    return session.get('role', None)

# --- Main & Auth Routes ---

@app.route('/')
def index():
    """Home page. Redirects to a dashboard if logged in."""
    user = get_user_session()
    role = get_user_role()
    if user and role == 'user':
        return redirect(url_for('user_dashboard'))
    if user and role == 'reviewer':
        return redirect(url_for('reviewer_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        role = request.form['role']
        
        user = None
        if role == 'user':
            user = db.find_user_by_email(email)
        elif role == 'reviewer':
            user = db.find_reviewer_by_email(email)
            
        if user:
            session['user'] = user
            session['role'] = role
            flash(f"Welcome back, {user['FirstName']}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid email or role. Please try again or create an account.", "danger")
            
    return render_template('login.html')

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        email = request.form['email']
        first_name = request.form['firstName']
        last_name = request.form['lastName']
        role = request.form['role']        
        existing = None
        if role == 'user':
            existing = db.find_user_by_email(email)
        elif role == 'reviewer':
            existing = db.find_reviewer_by_email(email)
        if existing:
            flash("An account with this email already exists.", "error")
            return redirect(url_for('login'))
        if role == 'user':
            db.create_user(first_name, last_name, email)
        elif role == 'reviewer':
            db.create_reviewer(first_name, last_name, email)
        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('create_account.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

# --- User Routes ---

@app.route('/user/dashboard')
def user_dashboard():
    user = get_user_session()
    role = get_user_role()
    if not user or role != 'user':
        flash("Please log in as a user.", "warning")
        return redirect(url_for('login'))        
    user_id = user['id']
    rejected_recipes = db.get_recipes_by_user(user_id, 'rejected')    
    has_rejected = len(rejected_recipes) > 0
    return render_template('user_dashboard.html', user=user, rejected_recipes=rejected_recipes, has_rejected=has_rejected)

@app.route('/user/add_recipe', methods=['GET', 'POST'])
def add_recipe():
    user = get_user_session()
    role = get_user_role()
    if not user or role != 'user':
        flash("Please log in as a user.", "warning")
        return redirect(url_for('login'))
    user_id = user['id']    
    rejected_recipes = db.get_recipes_by_user(user_id, 'rejected')
    if rejected_recipes:
        flash("You cannot add a new recipe while you have a rejected recipe. Please modify it first.", "danger")
        return redirect(url_for('user_dashboard'))
    if request.method == 'POST':
        price = request.form['price']
        is_vegan = 'is_vegan' in request.form
        ingredient_ids = request.form.getlist('ingredients')
        db.create_recipe(user_id, price, is_vegan, ingredient_ids)
        flash("Recipe submitted successfully!", "success")
        return redirect(url_for('user_dashboard'))        
    ingredients = db.get_all_ingredients()
    return render_template('add_recipe.html', ingredients=ingredients)

@app.route('/user/edit_rejected/<recipe_id>', methods=['GET', 'POST'])
def edit_rejected_recipe(recipe_id):
    user = get_user_session()
    role = get_user_role()
    if not user or role != 'user':
        flash("Please log in as a user.", "warning")
        return redirect(url_for('login'))
        
    recipe = db.get_recipe_by_id(recipe_id)
    if not recipe or recipe['status'] != 'rejected' or recipe['userID'][0] != user['id']:
        flash("Recipe not found or access denied.", "error")
        return redirect(url_for('user_dashboard'))
    if request.method == 'POST':
        is_vegan = 'is_vegan' in request.form
        ingredient_ids = request.form.getlist('ingredients') # Gets list of Record IDs
        db.update_rejected_recipe(recipe_id, is_vegan, ingredient_ids)
        flash("Recipe modified and resubmitted for review.", "success")
        return redirect(url_for('user_dashboard'))

    all_ingredients = db.get_all_ingredients()    
    current_ingredient_ids = recipe.get('Ingredients', [])
    return render_template(
        'edit_rejected_recipe.html', 
        recipe=recipe, 
        all_ingredients=all_ingredients,
        current_ingredient_ids=current_ingredient_ids
    )

# --- Reviewer Routes ---

@app.route('/reviewer/dashboard')
def reviewer_dashboard():
    reviewer = get_user_session()
    role = get_user_role()
    if not reviewer or role != 'reviewer':
        flash("Please log in as a reviewer.", "warning")
        return redirect(url_for('login'))
    reviewer_id = reviewer['id']    
    in_progress_recipe = db.get_recipes_by_reviewer(reviewer_id, 'inProgress')
    unassigned_recipes = []
    has_in_progress = bool(in_progress_recipe)
    if not has_in_progress:
        unassigned_recipes = db.get_unassigned_recipes()    
    all_ingredients = db.get_all_ingredients()        
    return render_template(
        'reviewer_dashboard.html', 
        reviewer=reviewer, 
        in_progress_recipe=in_progress_recipe[0] if has_in_progress else None,
        unassigned_recipes=unassigned_recipes,
        has_in_progress=has_in_progress,
        all_ingredients=all_ingredients
    )

@app.route('/reviewer/add_ingredient', methods=['POST'])
def add_ingredient():
    reviewer = get_user_session()
    role = get_user_role()
    if not reviewer or role != 'reviewer':
        flash("Not authorized.", "danger")
        return redirect(url_for('login'))
    ingredient_name = request.form['ingredient_name']
    if ingredient_name:
        db.add_ingredient(ingredient_name)
        flash(f"Ingredient '{ingredient_name}' added.", "success")
    else:
        flash("Ingredient name cannot be empty.", "warning")
    return redirect(url_for('reviewer_dashboard'))

@app.route('/reviewer/assign/<recipe_id>')
def assign_recipe(recipe_id):
    reviewer = get_user_session()
    role = get_user_role()
    if not reviewer or role != 'reviewer':
        flash("Not authorized.", "danger")
        return redirect(url_for('login'))
        
    reviewer_id = reviewer['id']
    in_progress_recipe = db.get_recipes_by_reviewer(reviewer_id, 'inProgress')
    if in_progress_recipe:
        flash("You already have a recipe in progress. Please review it first.", "danger")
        return redirect(url_for('reviewer_dashboard'))
    db.assign_recipe_to_reviewer(recipe_id, reviewer_id)
    flash("Recipe assigned to you.", "success")
    return redirect(url_for('reviewer_dashboard'))

@app.route('/reviewer/review/<recipe_id>', methods=['POST'])
def review_recipe(recipe_id):
    reviewer = get_user_session()
    role = get_user_role()
    if not reviewer or role != 'reviewer':
        flash("Not authorized.", "danger")
        return redirect(url_for('login'))
    recipe = db.get_recipe_by_id(recipe_id)
    if not recipe or recipe.get('reviewerID', [''])[0] != reviewer['id']:
        flash("This recipe is not assigned to you.", "danger")
        return redirect(url_for('reviewer_dashboard'))
    user_id_to_update = recipe.get('userID', [None])[0]
    if not user_id_to_update:
        flash("Error: Recipe is not linked to a user.", "danger")
        return redirect(url_for('reviewer_dashboard'))
    action = request.form['action'] # 'approve' or 'reject'
    if action == 'approve':
        db.update_recipe_status(recipe_id, 'approved', user_id_to_update)
        flash("Recipe approved!", "success")
    elif action == 'reject':
        db.update_recipe_status(recipe_id, 'rejected', user_id_to_update)
        flash("Recipe rejected.", "warning")
    return redirect(url_for('reviewer_dashboard'))


# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True)