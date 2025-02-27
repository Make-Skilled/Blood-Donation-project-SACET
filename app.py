from flask import Flask, request, render_template, session, redirect, url_for, flash, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId  
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "1234567890"

client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["bloodDonation"]
users = db["users"]
donations = db["donations"]
requests = db["requests"]
events = db["events"]  # Added events collection

ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

@app.route("/")
def landing():
    if "user_id" in session:
        user_id = session["user_id"]
        user = users.find_one({"_id": ObjectId(user_id)})
        return render_template("dashboard.html", user=user)
    
    # Get only 3 upcoming events
    upcoming_events = list(events.find({"date": {"$gte": datetime.now()}}).sort("date", 1).limit(3))
    return render_template("landing.html", events=upcoming_events)

@app.route("/signup")
def signup():
    return render_template("donor_register.html")

@app.route("/loginpage")
def loginpage():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please log in to access the dashboard", "warning")
        return redirect(url_for("loginpage"))

    # Get user's donations and upcoming events
    user_donations = list(donations.find({"uploaded_by": session["email"]}))
    upcoming_events = list(events.find({"date": {"$gte": datetime.now()}}).sort("date", 1))
    
    return render_template("dashboard.html", donations=user_donations, events=upcoming_events)


@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username")
    email = request.form.get("email")
    blood_group = request.form.get("bloodGroup")
    password = request.form.get("password")

    if not username or not email or not blood_group or not password:
        return render_template("donor_register.html", message="All fields are required")

    if users.find_one({"email": email}):
        return render_template("donor_register.html", message="Email already registered")

    hashed_password = generate_password_hash(password)
    user_data = {
        "username": username,
        "email": email,
        "bloodGroup": blood_group,
        "password": hashed_password,
        "createdAt": datetime.utcnow()
    }

    result = users.insert_one(user_data)
    if result.inserted_id:
        return render_template("donor_register.html", message="Registered Successfully")
    else:
        return render_template("donor_register.html", message="Error while registering the User")


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        flash("Email and password are required", "danger")
        return redirect(url_for("loginpage"))
    
    # Find user in MongoDB
    user = users.find_one({"email": email})
    if not user or not check_password_hash(user["password"], password):
        flash("Invalid email or password", "danger")
        return redirect(url_for("loginpage"))

    # Store user info in session
    session["user_id"] = str(user["_id"])
    session["username"] = user["username"]
    session["email"] = user["email"]

    flash(f"Welcome back, {user['username']}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/add-donation")
def add_donation():
    if "user_id" not in session:
        flash("Please log in to add a donation", "warning")
        return redirect(url_for("loginpage"))

    return render_template("add_donation.html")

@app.route("/show-requests")
def show_requests():
    if "user_id" not in session:
        flash("Please log in to view your requests", "warning")
        return redirect(url_for("loginpage"))

    # Fetch only the requests made by the logged-in user
    user_requests = requests.find({"receiverEmail": session["email"]})
    return render_template("show_requests.html", requests=user_requests)

@app.route("/my-donations")
def my_donations():
    if "user_id" not in session:
        flash("Please log in to view your donations", "warning")
        return redirect(url_for("loginpage"))

    # Fetch donations made by the logged-in user
    user_donations = donations.find({"uploaded_by": session["email"]})
    return render_template("my_donations.html", donations=user_donations)

@app.route("/submit-donation", methods=["POST"])
def submit_donation():
    if "user_id" not in session:
        flash("Please log in to add a donation", "warning")
        return redirect(url_for("loginpage"))

    donor_name = request.form.get("donorName")
    blood_group = request.form.get("bloodGroup")
    quantity = request.form.get("quantity")
    gender = request.form.get("gender")
    age = request.form.get("age")
    address = request.form.get("address")
    mobile_no = request.form.get("mobileNo")

    if not donor_name or not blood_group or not quantity or not gender or not age or not address or not mobile_no:
        flash("All fields are required", "danger")
        return redirect(url_for("add_donation"))

    try:
        donation_data = {
            "user_id": session["user_id"],
            "uploaded_by": session["email"],  # Add uploaded_by field
            "donorName": donor_name,
            "bloodGroup": blood_group,
            "quantity": int(quantity),
            "gender": gender,
            "age": int(age),
            "address": address,
            "mobileNo": mobile_no,
            "donationDate": datetime.utcnow()
        }

        donations.insert_one(donation_data)
        flash("Donation added successfully!", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        flash(f"Error adding donation: {str(e)}", "danger")
        return redirect(url_for("add_donation"))

@app.route("/submit-request", methods=["POST"])
def submit_request():
    if "user_id" not in session:
        flash("Please log in to make a request", "warning")
        return redirect(url_for("loginpage"))

    try:
        donation_id = request.form.get("donationId")
        donor_email = request.form.get("donorEmail")
        donor_mobile = request.form.get("donorMobile")
        required_units = int(request.form.get("requiredUnits"))
        receiver_mobile = request.form.get("receiverMobile")
        receiver_email = session.get("email")  # Get requester's email from session

        # Get the donation details
        donation = donations.find_one({"_id": ObjectId(donation_id)})
        
        if not donation:
            flash("Donation not found", "error")
            return redirect(url_for("dashboard"))

        if required_units > donation["quantity"]:
            flash(f"Only {donation['quantity']} units available", "error")
            return redirect(url_for("dashboard"))

        # Create the request
        request_data = {
            "donationId": ObjectId(donation_id),
            "donorEmail": donor_email,
            "donorMobile": donor_mobile,
            "receiverEmail": receiver_email,  # Add requester's email
            "receiverMobile": receiver_mobile,
            "bloodGroup": donation["bloodGroup"],
            "requiredUnits": required_units,
            "status": "Pending",
            "requestDate": datetime.utcnow()
        }

        # Insert the request
        requests.insert_one(request_data)
        flash("Blood request submitted successfully!", "success")
        return redirect(url_for("show_requests"))

    except Exception as e:
        flash(f"Error submitting request: {str(e)}", "error")
        return redirect(url_for("dashboard"))

@app.route("/get-donation-requests/<donation_id>")
def get_donation_requests(donation_id):
    if "user_id" not in session:
        return jsonify({"error": "Not authorized"}), 401

    try:
        # Verify this donation belongs to the logged-in user
        donation = donations.find_one({
            "_id": ObjectId(donation_id),
            "uploaded_by": session["email"]
        })

        if not donation:
            return jsonify({"error": "Donation not found"}), 404

        # Get all requests for this donation
        donation_requests = list(requests.find({"donationId": ObjectId(donation_id)}))
        
        # Convert ObjectId to string for JSON serialization
        for request in donation_requests:
            request["_id"] = str(request["_id"])
            request["donationId"] = str(request["donationId"])

        return jsonify({"requests": donation_requests})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update-request-status", methods=["POST"])
def update_request_status():
    if "user_id" not in session:
        return jsonify({"error": "Not authorized"}), 401

    try:
        data = request.json
        request_id = data.get("requestId")
        new_status = data.get("status")

        if not request_id or not new_status:
            return jsonify({"error": "Missing required fields"}), 400

        # Get the request
        blood_request = requests.find_one({"_id": ObjectId(request_id)})
        if not blood_request:
            return jsonify({"error": "Request not found"}), 404

        # Verify the donation belongs to the logged-in user
        donation = donations.find_one({
            "_id": blood_request["donationId"],
            "uploaded_by": session["email"]
        })
        if not donation:
            return jsonify({"error": "Not authorized to update this request"}), 403

        # Update the request status
        requests.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": {"status": new_status}}
        )

        return jsonify({
            "success": True,
            "donationId": str(blood_request["donationId"])
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("landing"))

# Admin Routes
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("username")
        password = request.form.get("password")

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["admin"] = True
            flash("Welcome Admin!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials", "error")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    try:
        # Get stats
        stats = {
            "total_donations": donations.count_documents({}),
            "total_requests": requests.count_documents({}),
            "total_users": users.count_documents({}),
            "active_events": events.count_documents({"date": {"$gte": datetime.now()}})
        }
        
        # Get upcoming events
        upcoming_events = list(events.find({"date": {"$gte": datetime.now()}}).sort("date", 1))
        
        # Get recent activities
        recent_donations = list(donations.find().sort("timestamp", -1).limit(5))
        recent_requests = list(requests.find().sort("timestamp", -1).limit(5))
        
        return render_template("admin_dashboard.html",
                             stats=stats,
                             events=upcoming_events,
                             recent_donations=recent_donations,
                             recent_requests=recent_requests)
    except Exception as e:
        print("Error in admin dashboard:", str(e))
        flash("Error loading dashboard data", "error")
        return render_template("admin_dashboard.html", stats={
            "total_donations": 0,
            "total_requests": 0,
            "total_users": 0,
            "active_events": 0
        }, events=[], recent_donations=[], recent_requests=[])

@app.route("/admin/add-event", methods=["POST"])
def add_event():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    try:
        event_date = datetime.strptime(request.form.get("date"), "%Y-%m-%d")
        event_time = datetime.strptime(request.form.get("time"), "%H:%M").time()
        
        event_data = {
            "eventName": request.form.get("eventName"),
            "organizedBy": request.form.get("organizedBy"),
            "location": request.form.get("location"),
            "date": event_date,
            "time": event_time.strftime("%H:%M"),
            "createdAt": datetime.utcnow()
        }
        print("Adding event:", event_data)  # Debug print
        result = events.insert_one(event_data)
        print("Event added with ID:", result.inserted_id)  # Debug print
        flash("Event added successfully!", "success")
    except Exception as e:
        print("Error adding event:", str(e))  # Debug print
        flash(f"Error adding event: {str(e)}", "error")

    return redirect(url_for("admin_dashboard"))

@app.route("/admin/events")
def admin_events():
    if not session.get("admin"):
        flash("Please login as admin", "error")
        return redirect(url_for("admin_login"))

    all_events = list(events.find().sort("date", -1))
    return render_template("admin_dashboard.html", events=all_events)

@app.route("/admin/delete-event/<event_id>", methods=["DELETE"])
def delete_event(event_id):
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        events.delete_one({"_id": ObjectId(event_id)})
        return jsonify({"message": "Event deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/donations")
def admin_donations():
    if not session.get("admin"):
        flash("Please login as admin", "error")
        return redirect(url_for("admin_login"))

    all_donations = list(donations.find())
    return render_template("admin_donations.html", donations=all_donations)

@app.route("/admin/requests")
def admin_requests():
    if not session.get("admin"):
        flash("Please login as admin", "error")
        return redirect(url_for("admin_login"))

    all_requests = list(requests.find())
    return render_template("admin_requests.html", requests=all_requests)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Logged out successfully", "success")
    return redirect(url_for("admin_login"))

@app.route("/events")
def view_events():
    try:
        upcoming_events = list(events.find({"date": {"$gte": datetime.now()}}).sort("date", 1))
        print("Found events:", len(upcoming_events))  # Debug print
        return render_template("events.html", events=upcoming_events)
    except Exception as e:
        print("Error fetching events:", str(e))  # Debug print
        flash("Error fetching events", "error")
        return render_template("events.html", events=[])

if __name__ == "__main__":
    app.run(port=3000, debug=True)
