import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # Allows HTTP for local testing

from flask import Flask, render_template, request, redirect, url_for, flash, session
from config import Config
import requests
from flask_dance.contrib.google import make_google_blueprint, google

from pathlib import Path
# ...
# Tell dotenv to load the file from the system config directory
app = Flask(__name__)
app.config.from_object(Config)

# Get the authorized domain from the environment file
AUTHORIZED_DOMAIN = os.environ.get("AUTHORIZED_DOMAIN")

# Setup for Google SSO using Flask-Dance
google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
)
app.register_blueprint(google_bp, url_prefix="/login")  

@app.route('/')
def index():
    if google.authorized:
        return redirect(url_for('request_access'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('index'))

@app.route('/request-access')
def request_access():
    if not google.authorized:
        flash("Please log in to continue.", "warning")
        return redirect(url_for("index"))

    try:
        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            flash("Failed to fetch your user info from Google.", "danger")
            return redirect(url_for('logout'))
        user_info = resp.json()
    except Exception as e:
        flash(f"Error fetching user info: {e}", "danger")
        return redirect(url_for('logout'))
        
    # --- THIS IS THE NEW VALIDATION LOGIC ---
    # Check if an authorized domain has been configured in the .env file
    if AUTHORIZED_DOMAIN:
        user_email = user_info.get("email", "").lower()
        # Check if the user's email address ends with the required domain
        if not user_email.endswith(AUTHORIZED_DOMAIN.lower()):
            # If it doesn't match, log the user out, show an error, and redirect to the login page.
            session.clear()
            flash(f"Access Denied. Please log in with a valid {AUTHORIZED_DOMAIN} account.", "danger")
            return redirect(url_for('index'))
    # --- END OF NEW LOGIC ---

    permissions = []
    try:
        response = requests.get(f"{app.config['API_BASE_URL']}/access/permissions")
        response.raise_for_status()
        permissions = response.json().get('permissions', [])
    except requests.exceptions.RequestException:
        flash("Could not load permissions from the backend.", "danger")

    return render_template('request_form.html', permissions=permissions, user_info=user_info)

@app.route('/submit-request', methods=['POST'])
def submit_request():
    if not google.authorized:
        return redirect(url_for("index"))
    
    user_email = request.form['userEmail']
    user_name = request.form['userName']
    permission_type = request.form['permissionType']
    access_type = request.form['accessType']
    jit_time_hours = request.form.get('jitTimeHours', '0')
    reason = request.form['reason']

    payload = {
        'userEmail': user_email, 'userName': user_name,
        'permissionType': permission_type, 'accessType': access_type,
        'jitTimeHours': float(jit_time_hours) if jit_time_hours.strip() else 0,
        'reason': reason
    }
    try:
        response = requests.post(f"{app.config['API_BASE_URL']}/access/request", json=payload)
        response.raise_for_status()
        # We no longer need to flash a success message, the page IS the message
    except Exception:
        flash("Failed to submit request to the backend.", "danger")
        # If it fails, redirect back to the form so they can see the error
        return redirect(url_for('request_access'))
        
    # If the try block succeeds, redirect to the new success page
    return redirect(url_for('success'))# Add this new route at the end of frontend-api/app.py

@app.route('/success')
def success():
    # Ensure the user is logged in to view this page
    if not google.authorized:
        return redirect(url_for("index"))

    # Get user info to display their name in the header
    user_info = {}
    try:
        resp = google.get("/oauth2/v2/userinfo")
        if resp.ok:
            user_info = resp.json()
    except Exception:
        # Fails silently, just won't show the name
        pass

    return render_template('success.html', user_info=user_info)

if __name__ == '__main__':
    app.run(debug=True, port=8000)
